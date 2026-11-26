"""Resource monitoring and recognition load control (FLOWS 5, 9.3; INFRA 6)."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Config
from app.content import texts
from app.db.requests import count_pending_circles
from app.services.intake import (
    IntakeClosure,
    IntakeReason,
    apply_automatic_closure,
    remove_automatic_closure,
)

logger = logging.getLogger(__name__)

CPU_CLOSE_THRESHOLD = 90.0
CPU_CLOSE_DURATION_SECONDS = 180.0
CPU_THROTTLE_THRESHOLD = 95.0
CPU_SAMPLE_SECONDS = 1.0
MIN_FREE_DISK_BYTES = 1024**3
MAX_QUEUE_LENGTH = 1000
RECOGNITION_WORKER_LIMIT = 1
THROTTLE_POLL_INTERVAL_SECONDS = 5.0


class MetricsReader(Protocol):
    """Reads system metrics without blocking the event loop."""

    async def cpu_percent(self) -> float:
        """Return the current total CPU load in percent."""

    async def free_disk_bytes(self, path: str | Path) -> int:
        """Return the free space in bytes on the filesystem at ``path``."""


class PsutilMetricsReader:
    """Default metrics reader based on psutil."""

    async def cpu_percent(self) -> float:
        import psutil

        return float(
            await asyncio.to_thread(
                psutil.cpu_percent,
                interval=CPU_SAMPLE_SECONDS,
            )
        )

    async def free_disk_bytes(self, path: str | Path) -> int:
        import psutil

        usage = await asyncio.to_thread(psutil.disk_usage, str(path))
        return int(usage.free)


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    """One monitor measurement and the automatic reasons it activated."""

    cpu_percent: float
    free_disk_bytes: int
    queue_length: int
    active_reasons: tuple[IntakeReason, ...]


class ResourceMonitor:
    """Periodically evaluate resource thresholds and update intake state."""

    def __init__(
        self,
        metrics: MetricsReader | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        cpu_close_duration: float = CPU_CLOSE_DURATION_SECONDS,
    ) -> None:
        self._metrics = metrics or PsutilMetricsReader()
        self._clock = clock
        self._cpu_close_duration = cpu_close_duration
        self._cpu_high_since: float | None = None

    async def check(
        self,
        session: AsyncSession,
        bot: Bot | None,
        config: Config,
    ) -> ResourceSnapshot:
        cpu_percent = await self._metrics.cpu_percent()
        free_disk_bytes = await self._metrics.free_disk_bytes(
            config.resource_monitor_disk_path
        )
        queue_length = await count_pending_circles(session)

        closures = self._closures(
            cpu_percent,
            free_disk_bytes,
            queue_length,
        )
        active_reasons = tuple(closure.reason for closure in closures)

        # Apply new reasons before removing old ones so a reason replacement
        # in one measurement cannot briefly reopen intake.
        for closure in closures:
            await apply_automatic_closure(session, bot, config, closure)

        for reason in (IntakeReason.CPU, IntakeReason.DISK, IntakeReason.QUEUE):
            if reason not in active_reasons:
                await remove_automatic_closure(session, bot, config, reason)

        return ResourceSnapshot(
            cpu_percent=cpu_percent,
            free_disk_bytes=free_disk_bytes,
            queue_length=queue_length,
            active_reasons=active_reasons,
        )

    def _closures(
        self,
        cpu_percent: float,
        free_disk_bytes: int,
        queue_length: int,
    ) -> tuple[IntakeClosure, ...]:
        closures: list[IntakeClosure] = []

        if self._is_cpu_sustained(cpu_percent):
            closures.append(
                IntakeClosure(
                    IntakeReason.CPU,
                    texts.format_intake_reason_cpu(round(cpu_percent)),
                )
            )
        if free_disk_bytes < MIN_FREE_DISK_BYTES:
            free_gb = free_disk_bytes / MIN_FREE_DISK_BYTES
            closures.append(
                IntakeClosure(
                    IntakeReason.DISK,
                    texts.format_intake_reason_disk(round(free_gb, 2)),
                )
            )
        if queue_length > MAX_QUEUE_LENGTH:
            closures.append(
                IntakeClosure(
                    IntakeReason.QUEUE,
                    texts.format_intake_reason_queue(queue_length),
                )
            )

        return tuple(closures)

    def _is_cpu_sustained(self, cpu_percent: float) -> bool:
        now = self._clock()
        if cpu_percent <= CPU_CLOSE_THRESHOLD:
            self._cpu_high_since = None
            return False

        if self._cpu_high_since is None:
            self._cpu_high_since = now
            return False

        return now - self._cpu_high_since >= self._cpu_close_duration


class RecognitionLoadController:
    """Reusable worker guard: one slot and CPU throttling above 95 percent."""

    def __init__(
        self,
        metrics: MetricsReader | None = None,
        *,
        worker_limit: int = RECOGNITION_WORKER_LIMIT,
        poll_interval: float = THROTTLE_POLL_INTERVAL_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if worker_limit < 1:
            raise ValueError("worker_limit must be positive")

        self._metrics = metrics or PsutilMetricsReader()
        self._worker_limit = worker_limit
        self._poll_interval = poll_interval
        self._sleep = sleep
        self._slots = asyncio.Semaphore(worker_limit)

    @property
    def worker_limit(self) -> int:
        return self._worker_limit

    async def wait_until_unthrottled(self) -> None:
        """Wait while total CPU load is above the throttling threshold."""
        while True:
            cpu_percent = await self._metrics.cpu_percent()
            if cpu_percent <= CPU_THROTTLE_THRESHOLD:
                return
            logger.warning(
                "Recognition worker is throttled: cpu=%.1f%%",
                cpu_percent,
            )
            await self._sleep(self._poll_interval)

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Acquire the single recognition slot and wait out CPU throttling."""
        async with self._slots:
            await self.wait_until_unthrottled()
            yield


async def run_resource_monitor(
    session_factory: async_sessionmaker[AsyncSession],
    bot: Bot | None,
    config: Config,
    *,
    monitor: ResourceMonitor | None = None,
    interval: float | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run periodic resource checks until cancelled or stopped."""
    resource_monitor = monitor or ResourceMonitor()
    delay = config.resource_monitor_interval if interval is None else interval

    while stop_event is None or not stop_event.is_set():
        try:
            async with session_factory() as session:
                snapshot = await resource_monitor.check(session, bot, config)
                await session.commit()
            logger.info(
                "Resource monitor: cpu=%.1f%% free_disk=%s queue=%s reasons=%s",
                snapshot.cpu_percent,
                snapshot.free_disk_bytes,
                snapshot.queue_length,
                ",".join(snapshot.active_reasons) or "none",
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Resource monitor iteration failed")

        await _wait_or_stop(delay, stop_event)


async def _wait_or_stop(
    interval: float,
    stop_event: asyncio.Event | None,
) -> None:
    if stop_event is None:
        await asyncio.sleep(interval)
        return

    try:
        await asyncio.wait_for(stop_event.wait(), timeout=interval)
    except TimeoutError:
        pass


__all__ = [
    "CPU_CLOSE_DURATION_SECONDS",
    "CPU_CLOSE_THRESHOLD",
    "CPU_SAMPLE_SECONDS",
    "CPU_THROTTLE_THRESHOLD",
    "MAX_QUEUE_LENGTH",
    "MIN_FREE_DISK_BYTES",
    "MetricsReader",
    "PsutilMetricsReader",
    "RECOGNITION_WORKER_LIMIT",
    "RecognitionLoadController",
    "ResourceMonitor",
    "ResourceSnapshot",
    "THROTTLE_POLL_INTERVAL_SECONDS",
    "run_resource_monitor",
]
