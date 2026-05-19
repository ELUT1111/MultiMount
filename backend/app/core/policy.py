from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.mount_permission_service import check_mount_access


FILE_ACTION_POLICIES = {
    "list": ("can_download", "read"),
    "info": ("can_download", "read"),
    "download": ("can_download", "read"),
    "share": ("can_download", "read"),
    "upload": ("can_upload", "readwrite"),
    "mkdir": ("can_upload", "readwrite"),
    "move": ("can_modify", "readwrite"),
    "copy": ("can_modify", "readwrite"),
    "delete": ("can_delete", "readwrite"),
}


def check_role_permission(user, permission: str) -> None:
    """检查角色/用户组基础权限。管理员沿用现有模型: 默认拥有全部基础权限。"""
    if user.role and user.role.name == "admin":
        return

    if user.role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未分配角色")

    permissions = user.role.permissions or {}
    if not permissions.get(permission, False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"缺少权限: {permission}",
        )


async def enforce_file_policy(db: AsyncSession, user, mount_id: int, action: str) -> str:
    """
    统一文件动作权限策略。

    保持现有模型:
    - 角色/用户组基础权限控制动作类型
    - 挂载所有者天然拥有自己挂载的读写权限
    - 所有者或管理员可继续通过 mount_permissions 给他人授予特定挂载权限
    - 角色级 mount_permissions 仍作为用户组级挂载访问权限
    """
    try:
        role_permission, mount_level = FILE_ACTION_POLICIES[action]
    except KeyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="未知文件权限策略")

    check_role_permission(user, role_permission)
    return await check_mount_access(db, mount_id, user, mount_level)
