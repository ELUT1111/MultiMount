"""
挂载点权限校验 — 基于用户级 + 角色级的 mount_permissions 检查。

用法:
    @router.get("/files/{mount_id}/list")
    async def list_files(mount_id: int, user=Depends(require_mount_access("read"))):
        ...
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.core.policy import enforce_file_policy
from app.services.mount_permission_service import check_mount_access


def require_mount_access(required_level: str = "read"):
    """
    挂载点权限依赖工厂。
    required_level: "read" 或 "readwrite"
    返回当前用户 (权限校验通过后)。

    权限优先级: admin → 挂载所有者 → 用户级权限 → 角色级权限 → 拒绝
    """

    async def _check(mount_id: int, current_user=Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
        await check_mount_access(db, mount_id, current_user, required_level)
        return current_user

    return _check


def check_basic_permission(permission: str):
    """
    基础权限检查依赖工厂。
    permission: "can_login" | "can_upload" | "can_download" | "can_modify" | "can_delete"
    """
    async def _check(current_user=Depends(get_current_user)):
        if current_user.role and current_user.role.name == "admin":
            return current_user

        role = current_user.role
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="未分配角色",
            )

        perms = role.permissions or {}
        if not perms.get(permission, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限: {permission}",
            )
        return current_user

    return _check


def require_file_action(action: str):
    """文件动作权限依赖工厂: 基础角色权限 + 挂载点授权。"""

    async def _check(mount_id: int, current_user=Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
        await enforce_file_policy(db, current_user, mount_id, action)
        return current_user

    return _check
