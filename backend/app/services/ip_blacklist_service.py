# IP 黑名单服务 — 管理黑名单 CRUD 并维护中间件内存缓存
from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ip_blacklist import IPBlacklist

logger = logging.getLogger("multimount.ip_blacklist")

# 内存缓存，供中间件 O(1) 查询
_blocked_ips: set[str] = set()


def is_blocked(ip: str) -> bool:
    """中间件调用: 检查 IP 是否被拉黑 (纯内存操作)"""
    return ip in _blocked_ips


async def refresh_cache(db: AsyncSession) -> None:
    """从数据库重建内存缓存，写操作后调用"""
    global _blocked_ips
    result = await db.execute(
        select(IPBlacklist.ip_address).where(IPBlacklist.is_active == True)  # noqa: E712
    )
    _blocked_ips = set(result.scalars().all())
    logger.info("IP 黑名单缓存已刷新, 共 %d 条", len(_blocked_ips))


async def get_all(db: AsyncSession) -> list[IPBlacklist]:
    """获取所有黑名单条目 (含已禁用)"""
    result = await db.execute(select(IPBlacklist).order_by(IPBlacklist.created_at.desc()))
    return list(result.scalars().all())


async def add(db: AsyncSession, ip_address: str, reason: str | None = None) -> IPBlacklist:
    """添加 IP 到黑名单，若已存在则重新激活"""
    result = await db.execute(select(IPBlacklist).where(IPBlacklist.ip_address == ip_address))
    entry = result.scalar_one_or_none()
    if entry:
        entry.is_active = True
        if reason:
            entry.reason = reason
    else:
        entry = IPBlacklist(ip_address=ip_address, reason=reason, is_active=True)
        db.add(entry)
    await db.flush()
    await refresh_cache(db)
    return entry


async def remove(db: AsyncSession, ip_address: str) -> bool:
    """从黑名单移除 IP (软删除)"""
    result = await db.execute(select(IPBlacklist).where(IPBlacklist.ip_address == ip_address))
    entry = result.scalar_one_or_none()
    if not entry:
        return False
    entry.is_active = False
    await db.flush()
    await refresh_cache(db)
    return True


async def init_cache(db: AsyncSession) -> None:
    """应用启动时加载缓存"""
    await refresh_cache(db)
