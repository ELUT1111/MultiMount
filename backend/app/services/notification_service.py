"""
通知服务 — 创建通知 + WebSocket 实时推送。
复用 transfer_service 的 WebSocket 连接管理模式。
"""
import logging
from collections import defaultdict

from sqlalchemy import delete as sa_delete, select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger("multimount.notification")

# 全局 WebSocket 连接管理 (按用户 ID 索引)
_notify_ws: dict[int, list] = {}
_PENDING_PUSHES_KEY = "notification_pending_pushes"


def _notification_payload(notif: Notification) -> dict:
    return {
        "id": notif.id,
        "type": notif.type,
        "title": notif.title,
        "content": notif.content,
        "is_read": notif.is_read,
        "is_archived": notif.is_archived,
        "related_id": notif.related_id,
        "metadata": notif.metadata_,
        "created_at": notif.created_at.isoformat(),
    }


def _is_pending_actionable(notif: Notification) -> bool:
    meta = notif.metadata_ or {}
    return notif.type == "access_request" and bool(meta.get("requester_id")) and not meta.get("action_status")


def _queue_push(db: AsyncSession, user_id: int, data: dict) -> None:
    pending = db.info.setdefault(_PENDING_PUSHES_KEY, defaultdict(list))
    pending[user_id].append(data)


async def flush_queued_pushes(db: AsyncSession) -> None:
    """事务提交后发送本次会话累积的通知推送。"""
    pending = db.info.pop(_PENDING_PUSHES_KEY, None)
    if not pending:
        return

    for user_id, messages in pending.items():
        for data in messages:
            await push_notification(user_id, data)


def clear_queued_pushes(db: AsyncSession) -> None:
    db.info.pop(_PENDING_PUSHES_KEY, None)


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
    metadata: dict | None = None,
) -> Notification:
    """创建通知，并在事务提交后推送到前端。"""
    notif = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        content=content,
        related_id=related_id,
        metadata_=metadata,
    )
    db.add(notif)
    await db.flush()
    await db.refresh(notif)

    _queue_push(db, user_id, {
        "type": "notification_new",
        "notification": _notification_payload(notif),
    })

    logger.info("通知已创建: type=%s user=%d title=%s", notification_type, user_id, title)
    return notif


async def get_notifications(
    db: AsyncSession,
    user_id: int,
    unread_only: bool = False,
    notification_type: str | None = None,
    pending_only: bool = False,
    include_archived: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """获取用户通知列表，支持筛选和分页。"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.is_read == False)
    if notification_type:
        query = query.where(Notification.type == notification_type)
    if pending_only:
        query = query.where(Notification.type == "access_request")
    if not include_archived:
        query = query.where(Notification.is_archived == False)

    if pending_only:
        result = await db.execute(query.order_by(Notification.created_at.desc()))
        filtered = [n for n in result.scalars().all() if _is_pending_actionable(n)]
        total = len(filtered)
        start = (page - 1) * page_size
        items = filtered[start:start + page_size]
    else:
        count_query = select(func.count()).select_from(query.order_by(None).subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        result = await db.execute(
            query.order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(result.scalars().all())

    return {
        "items": [_notification_payload(n) for n in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < total,
    }


async def list_notification_types(db: AsyncSession, user_id: int, include_archived: bool = False) -> list[str]:
    """获取当前用户已有的通知类型。"""
    query = select(Notification.type).where(Notification.user_id == user_id)
    if not include_archived:
        query = query.where(Notification.is_archived == False)
    query = query.distinct().order_by(Notification.type)
    result = await db.execute(query)
    return [row[0] for row in result.all()]


async def get_unread_count(db: AsyncSession, user_id: int) -> int:
    """获取未读通知数"""
    result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == user_id)
        .where(Notification.is_read == False)
        .where(Notification.is_archived == False)
    )
    return result.scalar() or 0


async def mark_read(db: AsyncSession, notification_id: int, user_id: int) -> int:
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
    _queue_push(db, user_id, {
        "type": "notification_count",
        "unread_count": count,
    })
    return count


async def mark_all_read(db: AsyncSession, user_id: int) -> int:
    """标记所有通知为已读"""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id)
        .where(Notification.is_read == False)
        .where(Notification.is_archived == False)
        .values(is_read=True)
    )
    await db.flush()

    _queue_push(db, user_id, {
        "type": "notification_count",
        "unread_count": 0,
    })
    return 0


async def queue_notification_update(db: AsyncSession, user_id: int, notif: Notification) -> None:
    """事务提交后推送已有通知的最新状态。"""
    _queue_push(db, user_id, {
        "type": "notification_update",
        "notification": _notification_payload(notif),
    })


async def archive_notification(db: AsyncSession, notification_id: int, user_id: int) -> int:
    """归档单条通知，归档后不再计入默认列表和未读数。"""
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == user_id)
    )
    notif = result.scalar_one_or_none()
    if notif:
        notif.is_archived = True
        notif.is_read = True
        await db.flush()
        await db.refresh(notif)
        _queue_push(db, user_id, {
            "type": "notification_update",
            "notification": _notification_payload(notif),
        })

    count = await get_unread_count(db, user_id)
    _queue_push(db, user_id, {
        "type": "notification_count",
        "unread_count": count,
    })
    return count


async def delete_notification(db: AsyncSession, notification_id: int, user_id: int) -> int:
    """删除单条通知。"""
    await db.execute(
        sa_delete(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == user_id)
    )
    await db.flush()

    count = await get_unread_count(db, user_id)
    _queue_push(db, user_id, {
        "type": "notification_delete",
        "notification_id": notification_id,
    })
    _queue_push(db, user_id, {
        "type": "notification_count",
        "unread_count": count,
    })
    return count
