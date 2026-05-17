"""
挂载权限管理 API — 授予/撤销/查看权限 + 权限申请 + 申请人查询。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.notification import Notification
from app.models.user import User
from app.services import mount_permission_service
from app.services.mount_service import get_mount

router = APIRouter()


class GrantRequest(BaseModel):
    user_id: int
    level: str = Field(..., pattern="^(read|readwrite)$")


class RequestAccessRequest(BaseModel):
    level: str = Field(..., pattern="^(read|readwrite)$")


async def _require_mount_owner_or_admin(mount_id: int, user: User, db: AsyncSession):
    """校验用户是挂载所有者或管理员"""
    is_admin = user.role and user.role.name == "admin"
    if is_admin:
        return
    mount = await get_mount(db, mount_id)
    if mount.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅挂载所有者或管理员可操作")


@router.get("/{mount_id}/permissions")
async def list_permissions(
    mount_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看挂载的用户权限列表"""
    await _require_mount_owner_or_admin(mount_id, user, db)
    perms = await mount_permission_service.list_mount_permissions(db, mount_id)
    return [
        {
            "user_id": p.user_id,
            "level": p.level,
            "granted_by": p.granted_by,
            "created_at": p.created_at,
        }
        for p in perms
    ]


@router.post("/{mount_id}/permissions", status_code=201)
async def grant_permission(
    mount_id: int,
    body: GrantRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """授予用户挂载权限"""
    await _require_mount_owner_or_admin(mount_id, user, db)
    perm = await mount_permission_service.grant_permission(
        db, mount_id, body.user_id, body.level, granted_by=user.id,
    )
    # 通知被授权用户
    from app.services.notification_service import create_notification
    mount = await get_mount(db, mount_id)
    await create_notification(
        db, body.user_id,
        "permission_granted",
        "权限授予",
        f"您已被授予挂载 \"{mount.name}\" 的 {body.level} 权限。",
        related_id=mount_id,
    )
    return {"message": "权限已授予", "user_id": body.user_id, "level": body.level}


@router.delete("/{mount_id}/permissions/{target_user_id}", status_code=204)
async def revoke_permission(
    mount_id: int,
    target_user_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """撤销用户挂载权限"""
    await _require_mount_owner_or_admin(mount_id, user, db)
    await mount_permission_service.revoke_permission(db, mount_id, target_user_id)


@router.post("/{mount_id}/request-access")
async def request_access(
    mount_id: int,
    body: RequestAccessRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """申请挂载访问权限"""
    await mount_permission_service.request_access(
        db, mount_id, user.id, body.level, user.username,
    )
    return {"message": "权限申请已发送"}


@router.get("/{mount_id}/requesters")
async def list_requesters(
    mount_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取曾向该挂载申请过权限的用户列表 (供权限管理对话框使用)"""
    await _require_mount_owner_or_admin(mount_id, user, db)

    # 查询 access_request 通知，从 metadata 中提取 requester_id
    result = await db.execute(
        select(Notification.metadata_)
        .where(Notification.type == "access_request")
        .where(Notification.related_id == mount_id)
    )
    requester_ids = set()
    for row in result.all():
        meta = row[0] or {}
        rid = meta.get("requester_id")
        if rid:
            requester_ids.add(rid)

    if not requester_ids:
        return []

    # 查询这些用户的 id 和 username
    users_result = await db.execute(
        select(User.id, User.username)
        .where(User.id.in_(requester_ids))
        .where(User.is_active == True)
    )
    return [{"id": row[0], "username": row[1]} for row in users_result.all()]
