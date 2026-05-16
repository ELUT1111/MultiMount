"""
挂载权限服务 — 用户级权限管理 + 权限检查。
权限优先级: admin → 挂载所有者 → 用户级权限 → 角色级权限 → 拒绝
"""
import logging

from fastapi import HTTPException, status
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mount import Mount
from app.models.mount_permission import MountPermission

logger = logging.getLogger("multimount.mount_perm")

LEVELS = {"none": 0, "read": 1, "readwrite": 2}


async def check_mount_access(db: AsyncSession, mount_id: int, user, required_level: str = "read") -> str:
    """
    检查用户对挂载点的访问权限，返回实际权限等级。
    权限不足时 raise HTTPException 403。
    """
    required = LEVELS.get(required_level, 1)

    # 1. 管理员 → 全部权限
    if user.role and user.role.name == "admin":
        return "readwrite"

    # 2. 挂载所有者 → 全部权限
    mount_result = await db.execute(select(Mount.user_id).where(Mount.id == mount_id))
    row = mount_result.first()
    if row and row[0] == user.id:
        return "readwrite"

    # 3. 用户级权限 (mount_permissions 表)
    perm_result = await db.execute(
        select(MountPermission.level)
        .where(MountPermission.mount_id == mount_id)
        .where(MountPermission.user_id == user.id)
    )
    perm_row = perm_result.first()
    if perm_row:
        user_level = LEVELS.get(perm_row[0], 0)
        if user_level >= required:
            return perm_row[0]

    # 4. 角色级权限 (role.mount_permissions JSON)
    role = user.role
    if role and role.mount_permissions:
        mount_perms = role.mount_permissions
        role_level_str = mount_perms.get(mount_id) or mount_perms.get(str(mount_id)) or "none"
        role_level = LEVELS.get(role_level_str, 0)
        if role_level >= required:
            return role_level_str

    # 5. 拒绝
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"无权访问此挂载点 (需要 {required_level} 权限)",
    )


async def grant_permission(db: AsyncSession, mount_id: int, user_id: int,
                           level: str, granted_by: int) -> MountPermission:
    """授予用户挂载权限 (upsert)"""
    if level not in ("read", "readwrite"):
        raise HTTPException(status_code=400, detail="权限等级必须为 read 或 readwrite")

    result = await db.execute(
        select(MountPermission)
        .where(MountPermission.mount_id == mount_id)
        .where(MountPermission.user_id == user_id)
    )
    perm = result.scalar_one_or_none()

    if perm:
        perm.level = level
        perm.granted_by = granted_by
    else:
        perm = MountPermission(
            mount_id=mount_id,
            user_id=user_id,
            level=level,
            granted_by=granted_by,
        )
        db.add(perm)

    await db.flush()
    await db.refresh(perm)
    return perm


async def revoke_permission(db: AsyncSession, mount_id: int, user_id: int) -> None:
    """撤销用户挂载权限"""
    await db.execute(
        sa_delete(MountPermission)
        .where(MountPermission.mount_id == mount_id)
        .where(MountPermission.user_id == user_id)
    )
    await db.flush()


async def list_mount_permissions(db: AsyncSession, mount_id: int) -> list[MountPermission]:
    """列出某挂载的所有用户权限"""
    result = await db.execute(
        select(MountPermission).where(MountPermission.mount_id == mount_id)
    )
    return list(result.scalars().all())


async def get_accessible_mount_ids(db: AsyncSession, user) -> set[int]:
    """返回用户可访问的所有挂载 ID 集合"""
    ids = set()

    # 管理员 → 全部挂载
    if user.role and user.role.name == "admin":
        result = await db.execute(select(Mount.id))
        return {row[0] for row in result.all()}

    # 自己创建的挂载
    result = await db.execute(select(Mount.id).where(Mount.user_id == user.id))
    ids.update(row[0] for row in result.all())

    # 用户级权限
    result = await db.execute(
        select(MountPermission.mount_id)
        .where(MountPermission.user_id == user.id)
        .where(MountPermission.level.in_(["read", "readwrite"]))
    )
    ids.update(row[0] for row in result.all())

    # 角色级权限
    if user.role and user.role.mount_permissions:
        for k, v in user.role.mount_permissions.items():
            if v in ("read", "readwrite"):
                try:
                    ids.add(int(k))
                except (ValueError, TypeError):
                    pass

    return ids


async def request_access(db: AsyncSession, mount_id: int, user_id: int,
                         requested_level: str, username: str) -> None:
    """发起权限申请 → 通知挂载所有者"""
    from app.services.notification_service import create_notification

    mount_result = await db.execute(select(Mount.user_id, Mount.name).where(Mount.id == mount_id))
    row = mount_result.first()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="挂载点不存在或无所有者")

    owner_id = row[0]
    mount_name = row[1]

    if owner_id == user_id:
        raise HTTPException(status_code=400, detail="无需申请自己挂载的权限")

    await create_notification(
        db, owner_id,
        "access_request",
        "权限申请",
        f"用户 \"{username}\" 申请 {requested_level} 权限访问您的挂载 \"{mount_name}\"。",
        related_id=mount_id,
    )
