from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Config
from app.content import texts
from app.db.enums import CircleStatus
from app.db.models import Circle
from app.db.requests import create_circle
from app.services import (
    MAX_QUEUE_LENGTH,
    MIN_FREE_DISK_BYTES,
    IntakeReason,
    PsutilMetricsReader,
    RecognitionLoadController,
    ResourceMonitor,
    ResourceSnapshot,
    automatic_closures,
    is_intake_closed,
    reset_automatic_closures,
    run_resource_monitor,
)

GIB = 1024**3


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class FakeMetrics:
    def __init__(
        self,
        *,
        cpu_percent: float = 0.0,
        free_disk_bytes: int = 10 * GIB,
    ) -> None:
        self.cpu = cpu_percent
        self.free = free_disk_bytes
        self.disk_paths: list[str] = []

    async def cpu_percent(self) -> float:
        return self.cpu

    async def free_disk_bytes(self, path: str | Path) -> int:
        self.disk_paths.append(str(path))
        return self.free


class SequenceMetrics(FakeMetrics):
    def __init__(self, values: list[float]) -> None:
        super().__init__()
        self._values = iter(values)

    async def cpu_percent(self) -> float:
        return next(self._values)


def make_config() -> Config:
    return Config(
        bot_token="123456:fake",
        admin_chat_id=-100,
        resource_monitor_interval=1,
        resource_monitor_disk_path="/data",
    )


@pytest.fixture(autouse=True)
def reset_monitor_state() -> Iterator[None]:
    reset_automatic_closures()
    yield
    reset_automatic_closures()


async def add_pending_circles(
    session: AsyncSession,
    count: int,
) -> None:
    for index in range(count):
        await create_circle(
            session,
            owner_hid=f"hid-{index}",
            file_id=f"file-{index}",
            duration=10,
            status=CircleStatus.PENDING_AUTO,
        )


@pytest.mark.asyncio
async def test_cpu_closes_only_after_three_minutes(
    session: AsyncSession,
    bot,
) -> None:
    clock = FakeClock()
    metrics = FakeMetrics(cpu_percent=91)
    monitor = ResourceMonitor(metrics, clock=clock)
    config = make_config()

    snapshot = await monitor.check(session, bot, config)
    assert snapshot.active_reasons == ()
    assert not await is_intake_closed(session, config)
    bot.send_message.assert_not_awaited()

    clock.advance(179)
    await monitor.check(session, bot, config)
    assert not await is_intake_closed(session, config)
    bot.send_message.assert_not_awaited()

    clock.advance(1)
    snapshot = await monitor.check(session, bot, config)
    assert snapshot.active_reasons == (IntakeReason.CPU,)
    assert await is_intake_closed(session, config)
    bot.send_message.assert_awaited_once()
    assert texts.format_intake_reason_cpu(91) in (
        bot.send_message.await_args.kwargs["text"]
    )

    metrics.cpu = 50
    clock.advance(1)
    snapshot = await monitor.check(session, bot, config)
    assert snapshot.active_reasons == ()
    assert not await is_intake_closed(session, config)
    assert bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_cpu_timer_resets_after_load_drop(
    session: AsyncSession,
    bot,
) -> None:
    clock = FakeClock()
    metrics = FakeMetrics(cpu_percent=91)
    monitor = ResourceMonitor(metrics, clock=clock)
    config = make_config()

    await monitor.check(session, bot, config)
    clock.advance(100)
    metrics.cpu = 50
    await monitor.check(session, bot, config)

    metrics.cpu = 91
    clock.advance(100)
    await monitor.check(session, bot, config)
    clock.advance(179)
    await monitor.check(session, bot, config)
    assert not await is_intake_closed(session, config)

    clock.advance(1)
    await monitor.check(session, bot, config)
    assert await is_intake_closed(session, config)


@pytest.mark.asyncio
async def test_disk_threshold_closes_and_reopens_intake(
    session: AsyncSession,
    bot,
) -> None:
    metrics = FakeMetrics(free_disk_bytes=MIN_FREE_DISK_BYTES)
    monitor = ResourceMonitor(metrics, clock=FakeClock())
    config = make_config()

    await monitor.check(session, bot, config)
    assert not await is_intake_closed(session, config)
    assert metrics.disk_paths == ["/data"]

    metrics.free = MIN_FREE_DISK_BYTES - 1
    snapshot = await monitor.check(session, bot, config)
    assert snapshot.active_reasons == (IntakeReason.DISK,)
    assert await is_intake_closed(session, config)
    assert texts.format_intake_reason_disk(1.0) in (
        bot.send_message.await_args.kwargs["text"]
    )

    metrics.free = MIN_FREE_DISK_BYTES
    snapshot = await monitor.check(session, bot, config)
    assert snapshot.active_reasons == ()
    assert not await is_intake_closed(session, config)
    assert bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_queue_threshold_closes_and_reopens_intake(
    session: AsyncSession,
    bot,
) -> None:
    await add_pending_circles(session, MAX_QUEUE_LENGTH)
    metrics = FakeMetrics()
    monitor = ResourceMonitor(metrics, clock=FakeClock())
    config = make_config()

    await monitor.check(session, bot, config)
    assert not await is_intake_closed(session, config)

    await add_pending_circles(session, 1)
    snapshot = await monitor.check(session, bot, config)
    assert snapshot.queue_length == MAX_QUEUE_LENGTH + 1
    assert snapshot.active_reasons == (IntakeReason.QUEUE,)
    assert await is_intake_closed(session, config)
    assert texts.format_intake_reason_queue(MAX_QUEUE_LENGTH + 1) in (
        bot.send_message.await_args.kwargs["text"]
    )

    await _delete_all_circles(session)

    snapshot = await monitor.check(session, bot, config)
    assert snapshot.active_reasons == ()
    assert not await is_intake_closed(session, config)
    assert bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_reason_replacement_does_not_reopen_intake(
    session: AsyncSession,
    bot,
) -> None:
    clock = FakeClock()
    metrics = FakeMetrics(cpu_percent=91)
    monitor = ResourceMonitor(metrics, clock=clock)
    config = make_config()

    await monitor.check(session, bot, config)
    clock.advance(180)
    await monitor.check(session, bot, config)
    assert await is_intake_closed(session, config)
    assert bot.send_message.await_count == 1

    metrics.cpu = 50
    metrics.free = MIN_FREE_DISK_BYTES - 1
    clock.advance(1)
    snapshot = await monitor.check(session, bot, config)

    assert snapshot.active_reasons == (IntakeReason.DISK,)
    assert await is_intake_closed(session, config)
    assert bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_multiple_reasons_reopen_only_after_all_clear(
    session: AsyncSession,
    bot,
) -> None:
    metrics = FakeMetrics(
        cpu_percent=91,
        free_disk_bytes=MIN_FREE_DISK_BYTES - 1,
    )
    await add_pending_circles(session, MAX_QUEUE_LENGTH + 1)
    clock = FakeClock()
    monitor = ResourceMonitor(metrics, clock=clock)
    config = make_config()

    await monitor.check(session, bot, config)
    clock.advance(180)
    snapshot = await monitor.check(session, bot, config)
    assert snapshot.active_reasons == (
        IntakeReason.CPU,
        IntakeReason.DISK,
        IntakeReason.QUEUE,
    )
    assert bot.send_message.await_count == 1

    metrics.free = 10 * GIB
    await _delete_all_circles(session)
    clock.advance(1)
    snapshot = await monitor.check(session, bot, config)
    assert snapshot.active_reasons == (IntakeReason.CPU,)
    assert await is_intake_closed(session, config)
    assert bot.send_message.await_count == 1

    metrics.cpu = 50
    await monitor.check(session, bot, config)
    assert not await is_intake_closed(session, config)
    assert bot.send_message.await_count == 2


async def _delete_all_circles(session: AsyncSession) -> None:
    await session.execute(delete(Circle))
    await session.flush()


@pytest.mark.asyncio
async def test_monitor_skips_notification_without_admin_chat(
    session: AsyncSession,
    bot,
) -> None:
    metrics = FakeMetrics(free_disk_bytes=MIN_FREE_DISK_BYTES - 1)
    monitor = ResourceMonitor(metrics, clock=FakeClock())
    config = Config(bot_token="123456:fake", admin_chat_id=None)

    snapshot = await monitor.check(session, bot, config)

    assert snapshot.active_reasons == (IntakeReason.DISK,)
    assert await is_intake_closed(session, config)
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_psutil_reader_reads_cpu_and_disk(monkeypatch) -> None:
    import psutil

    calls: dict[str, object] = {}

    def fake_cpu_percent(*, interval: float) -> float:
        calls["interval"] = interval
        return 42.5

    def fake_disk_usage(path: str) -> object:
        calls["path"] = path
        return type("Usage", (), {"free": 1234})()

    monkeypatch.setattr(psutil, "cpu_percent", fake_cpu_percent)
    monkeypatch.setattr(psutil, "disk_usage", fake_disk_usage)

    reader = PsutilMetricsReader()

    assert await reader.cpu_percent() == 42.5
    assert await reader.free_disk_bytes("/data") == 1234
    assert calls["path"] == "/data"
    assert calls["interval"] > 0


@pytest.mark.asyncio
async def test_load_controller_rejects_invalid_worker_limit() -> None:
    with pytest.raises(ValueError):
        RecognitionLoadController(FakeMetrics(), worker_limit=0)


@pytest.mark.asyncio
async def test_load_controller_waits_for_cpu_below_95() -> None:
    metrics = SequenceMetrics([97.0, 96.0, 95.0])
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    controller = RecognitionLoadController(
        metrics,
        poll_interval=3,
        sleep=fake_sleep,
    )

    await controller.wait_until_unthrottled()

    assert sleeps == [3, 3]


@pytest.mark.asyncio
async def test_load_controller_allows_one_slot() -> None:
    controller = RecognitionLoadController(FakeMetrics())
    running = 0
    peak = 0

    async def job() -> None:
        nonlocal running, peak
        async with controller.slot():
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0)
            running -= 1

    await asyncio.gather(*(job() for _ in range(3)))

    assert controller.worker_limit == 1
    assert peak == 1


@pytest.mark.asyncio
async def test_run_resource_monitor_stops_by_event(
    db_engine,
) -> None:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    stop_event = asyncio.Event()

    class StoppingMonitor:
        calls = 0

        async def check(
            self,
            session: AsyncSession,
            bot: Any,
            config: Config,
        ) -> Any:
            self.calls += 1
            stop_event.set()
            return ResourceSnapshot(
                cpu_percent=0.0,
                free_disk_bytes=10 * GIB,
                queue_length=0,
                active_reasons=(),
            )

    monitor = StoppingMonitor()
    await asyncio.wait_for(
        run_resource_monitor(
            session_factory,
            None,
            make_config(),
            monitor=monitor,
            interval=0.01,
            stop_event=stop_event,
        ),
        timeout=1,
    )

    assert monitor.calls == 1


@pytest.mark.asyncio
async def test_monitor_returns_metrics(
    session: AsyncSession,
    bot,
) -> None:
    metrics = FakeMetrics(cpu_percent=12.5, free_disk_bytes=3 * GIB)
    monitor = ResourceMonitor(metrics, clock=FakeClock())

    snapshot = await monitor.check(session, bot, make_config())

    assert snapshot.cpu_percent == 12.5
    assert snapshot.free_disk_bytes == 3 * GIB
    assert snapshot.queue_length == 0
    assert automatic_closures() == ()
