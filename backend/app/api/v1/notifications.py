"""
通知 API — WebSocket 推送 + REST 查询/标记已读 + 可执行通知处理。
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
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
    type: str | None = Query(default=None),
    pending_only: bool = False,
    include_archived: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的通知列表"""
    return await notification_service.get_notifications(
        db,
        user.id,
        unread_only=unread_only,
        notification_type=type,
        pending_only=pending_only,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )


@router.get("/types")
async def list_notification_types(
    include_archived: bool = False,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户已有的通知类型"""
    types = await notification_service.list_notification_types(db, user.id, include_archived)
    return {"types": types}


@router.get("/unread-count")
async def unread_count(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取未读通知数"""
    count = await notification_service.get_unread_count(db, user.id)
    return {"unread_count": count}


@router.put("/read-all")
async def mark_all_read(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记所有通知为已读"""
    unread_count = await notification_service.mark_all_read(db, user.id)
    return {"ok": True, "unread_count": unread_count}


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记单条通知为已读"""
    unread_count = await notification_service.mark_read(db, notification_id, user.id)
    return {"ok": True, "unread_count": unread_count}


@router.put("/{notification_id}/archive")
async def archive_notification(
    notification_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """归档单条通知"""
    unread_count = await notification_service.archive_notification(db, notification_id, user.id)
    return {"ok": True, "unread_count": unread_count}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除单条通知"""
    unread_count = await notification_service.delete_notification(db, notification_id, user.id)
    return {"ok": True, "unread_count": unread_count}


# ── 可执行通知处理 ──────────────────────────────────────────

class NotificationAction(BaseModel):
    action: Literal["approve", "deny"]


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

    if meta.get("action_status") in {"approved", "denied"}:
        raise HTTPException(status_code=400, detail="该通知已处理")

    # 校验当前用户是挂载所有者或管理员
    is_admin = user.role and user.role.name == "admin"
    mount = await get_mount(db, mount_id)
    if not is_admin and mount.user_id != user.id:
        raise HTTPException(status_code=403, detail="仅挂载所有者可审批")

    if body.action == "approve":
        # 授予权限
        await mount_permission_service.grant_permission(
            db, mount_id, requester_id, requested_level, granted_by=user.id,
        )
        # 通知申请人
        await notification_service.create_notification(
            db, requester_id,
            "permission_granted", "权限授予",
            f"您的权限申请已通过，您已被授予挂载 \"{mount.name}\" 的 {requested_level} 权限。",
            related_id=mount_id,
        )
        action_status = "approved"
        action_label = "已同意"
    else:
        await notification_service.create_notification(
            db, requester_id,
            "permission_denied", "权限申请被拒绝",
            f"您对挂载 \"{mount.name}\" 的 {requested_level} 权限申请已被拒绝。",
            related_id=mount_id,
        )
        action_status = "denied"
        action_label = "已拒绝"

    notif.metadata_ = {
        **meta,
        "action_status": action_status,
        "action_by": user.id,
    }
    await db.flush()
    await db.refresh(notif)

    # 标记通知已读
    unread_count = await notification_service.mark_read(db, notification_id, user.id)
    await db.refresh(notif)
    await notification_service.queue_notification_update(db, user.id, notif)

    return {"message": f"权限申请{action_label}", "unread_count": unread_count}
