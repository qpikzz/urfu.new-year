"""Key-value runtime settings (DATA 5)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Setting


async def get_setting(session: AsyncSession, key: str) -> str | None:
    setting = await session.get(Setting, key)
    return None if setting is None else setting.value


async def set_setting(
    session: AsyncSession,
    key: str,
    value: str,
) -> Setting:
    setting = await session.get(Setting, key)
    if setting is None:
        setting = Setting(key=key, value=value)
        session.add(setting)
    else:
        setting.value = value

    await session.flush()
    return setting


async def delete_setting(session: AsyncSession, key: str) -> bool:
    setting = await session.get(Setting, key)
    if setting is None:
        return False
    await session.delete(setting)
    await session.flush()
    return True
