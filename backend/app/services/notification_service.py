"""
通知服务 — 创建通知 + WebSocket 实时推送。
复用 transfer_service 的 WebSocket 连接管理模式。
"""
import logging

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger("multimount.notification")

# 全局 WebSocket 连接管理 (按用户 ID 索引)
_notify_ws: dict[int, list] = {}


def register_notify_ws(user_id: int, ws):
    """注册通知 WebSocket 连接"""
    _notify_ws.setdefault(user_id, []).append(ws)


def unregister_notify_ws(user_id: int, ws):
    """注销通知 WebSocket 连接"""
    conns = _notify_ws.get(user_id, [])
    if ws in conns:
        conns.remove(ws)


async def push_notification(user_id: int, data: dict):
    """向指定用户的所有 WebSocket 连接推送通知"""
    conns = _notify_ws.get(user_id, [])
    if not conns:
        return
    for ws in conns[:]:
        try:
            await ws.send_json(data)
        except Exception:
            conns.remove(ws)


async def create_notification(
    db: AsyncSession,
    user_id: int,
    notification_type: str,
    title: str,
    content: str,
    related_id: int | None = None,
) -> Notification:
    """创建通知并推送到前端"""
    notif = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        content=content,
        related_id=related_id,
    )
    db.add(notif)
    await db.flush()
    await db.refresh(notif)

    # WebSocket 推送
    await push_notification(user_id, {
        "type": "notification_new",
        "notification": {
            "id": notif.id,
            "type": notif.type,
            "title": notif.title,
            "content": notif.content,
            "is_read": notif.is_read,
            "related_id": notif.related_id,
            "created_at": notif.created_at.isoformat(),
        },
    })

    logger.info("通知已创建: type=%s user=%d title=%s", notification_type, user_id, title)
    return notif


async def get_notifications(
    db: AsyncSession, user_id: int, unread_only: bool = False
) -> list[Notification]:
    """获取用户通知列表"""
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.is_read == False)
    query = query.order_by(Notification.created_at.desc()).limit(100)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_unread_count(db: AsyncSession, user_id: int) -> int:
    """获取未读通知数"""
    result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == user_id)
        .where(Notification.is_read == False)
    )
    return result.scalar() or 0


async def mark_read(db: AsyncSession, notification_id: int, user_id: int) -> None:
    """标记单条通知为已读"""
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == user_id)
        .values(is_read=True)
    )
    await db.flush()

    # 推送未读数更新
    count = await get_unread_count(db, user_id)
    await push_notification(user_id, {
        "type": "notification_count",
        "unread_count": count,
    })


async def mark_all_read(db: AsyncSession, user_id: int) -> None:
    """标记所有通知为已读"""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id)
        .where(Notification.is_read == False)
        .values(is_read=True)
    )
    await db.flush()

    await push_notification(user_id, {
        "type": "notification_count",
        "unread_count": 0,
    })
