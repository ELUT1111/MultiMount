"""
通知 API — WebSocket 推送 + REST 查询/标记已读。
"""
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.services import notification_service

logger = logging.getLogger("multimount.api.notifications")

router = APIRouter()


# ── WebSocket 端点 ─────────────────────────────────────────

@router.websocket("/ws")
async def notification_ws(websocket: WebSocket):
    """通知 WebSocket — 实时推送新通知和未读数"""
    await websocket.accept()

    # 从 query param 获取 token 并验证用户
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4001, reason="缺少 token")
        return

    from app.core.security import decode_token

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=4001, reason="token 无效")
        return

    user_id = int(payload["sub"])
    notification_service.register_notify_ws(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        notification_service.unregister_notify_ws(user_id, websocket)


# ── REST 端点 ──────────────────────────────────────────────

@router.get("")
async def list_notifications(
    unread_only: bool = False,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的通知列表"""
    notifs = await notification_service.get_notifications(db, user.id, unread_only)
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "content": n.content,
            "is_read": n.is_read,
            "related_id": n.related_id,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifs
    ]


@router.get("/unread-count")
async def unread_count(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取未读通知数"""
    count = await notification_service.get_unread_count(db, user.id)
    return {"unread_count": count}


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记单条通知为已读"""
    await notification_service.mark_read(db, notification_id, user.id)
    return {"ok": True}


@router.put("/read-all")
async def mark_all_read(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记所有通知为已读"""
    await notification_service.mark_all_read(db, user.id)
    return {"ok": True}
