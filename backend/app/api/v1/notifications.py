"""
通知 API — WebSocket 推送 + REST 查询/标记已读 + 可执行通知处理。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.notification import Notification
from app.services import notification_service

logger = logging.getLogger("multimount.api.notifications")

router = APIRouter()


# ── WebSocket 端点 ─────────────────────────────────────────

@router.websocket("/ws")
async def notification_ws(websocket: WebSocket):
    """通知 WebSocket — 实时推送新通知和未读数"""
    # 从 Sec-WebSocket-Protocol 头提取 token (客户端通过 subprotocol 传递)
    token = ""
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    if protocols:
        parts = [p.strip() for p in protocols.split(",")]
        if len(parts) >= 2 and parts[0] == "auth":
            token = parts[1]

    # 回退: 也支持 query param (兼容旧客户端)
    if not token:
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
    await websocket.accept(subprotocol="auth")
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
            "metadata": n.metadata_,
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


# ── 可执行通知处理 ──────────────────────────────────────────

class NotificationAction(BaseModel):
    action: str  # "approve" | "deny"


@router.post("/{notification_id}/action")
async def handle_notification_action(
    notification_id: int,
    body: NotificationAction,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """处理可执行通知 (如权限申请的同意/拒绝)"""
    from sqlalchemy import select as sa_select
    from app.services import mount_permission_service
    from app.services.mount_service import get_mount

    # 获取通知
    result = await db.execute(
        sa_select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="通知不存在")
    if notif.type != "access_request":
        raise HTTPException(status_code=400, detail="该通知不支持此操作")

    meta = notif.metadata_ or {}
    requester_id = meta.get("requester_id")
    requested_level = meta.get("requested_level")
    mount_id = notif.related_id

    if not requester_id or not requested_level or not mount_id:
        raise HTTPException(status_code=400, detail="通知数据不完整")

    if body.action == "approve":
        # 校验当前用户是挂载所有者或管理员
        is_admin = user.role and user.role.name == "admin"
        if not is_admin:
            mount = await get_mount(db, mount_id)
            if mount.user_id != user.id:
                raise HTTPException(status_code=403, detail="仅挂载所有者可审批")

        # 授予权限
        await mount_permission_service.grant_permission(
            db, mount_id, requester_id, requested_level, granted_by=user.id,
        )
        # 通知申请人
        mount = await get_mount(db, mount_id)
        await notification_service.create_notification(
            db, requester_id,
            "permission_granted", "权限授予",
            f"您的权限申请已通过，您已被授予挂载 \"{mount.name}\" 的 {requested_level} 权限。",
            related_id=mount_id,
        )

    # 标记通知已读
    await notification_service.mark_read(db, notification_id, user.id)

    action_label = "已同意" if body.action == "approve" else "已拒绝"
    return {"message": f"权限申请{action_label}"}
