"""
挂载点权限校验 — 基于角色的 mount_permissions 检查用户对指定挂载点的访问权限。

用法:
    @router.get("/files/{mount_id}/list")
    async def list_files(mount_id: int, user=Depends(require_mount_access("read"))):
        ...
"""
import logging
from functools import wraps

from fastapi import Depends, HTTPException, status

from app.dependencies import get_current_user

logger = logging.getLogger("multimount.permissions")


def require_mount_access(required_level: str = "read"):
    """
    挂载点权限依赖工厂。
    required_level: "read" 或 "readwrite"
    返回一个 FastAPI 依赖函数, 校验当前用户对路径参数中 mount_id 的权限。

    权限等级:
      - "none": 不可见
      - "read": 只读 (列表/下载)
      - "readwrite": 读写 (上传/删除/移动/复制)
    """
    levels = {"none": 0, "read": 1, "readwrite": 2}
    required = levels.get(required_level, 1)

    async def _check(mount_id: int, current_user=Depends(get_current_user)):
        # 管理员拥有全部权限
        if current_user.role and current_user.role.name == "admin":
            return current_user

        role = current_user.role
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="未分配角色, 无法访问挂载点",
            )

        mount_perms = role.mount_permissions or {}
        # mount_permissions 的 key 可能是 int 或 str
        user_level_str = mount_perms.get(mount_id) or mount_perms.get(str(mount_id)) or "none"
        user_level = levels.get(user_level_str, 0)

        if user_level < required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"无权访问此挂载点 (需要 {required_level}, 当前 {user_level_str})",
            )
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
