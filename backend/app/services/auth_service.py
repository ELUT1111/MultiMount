import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, ConflictException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.role import Role
from app.models.user import User

logger = logging.getLogger("multimount.auth")


async def register(db: AsyncSession, account: str, username: str, email: str, password: str) -> User:
    """注册新用户, 默认分配普通用户角色"""
    # 检查账号/用户名/邮箱是否已存在
    existing = await db.execute(
        select(User).where(
            (User.account == account) | (User.username == username) | (User.email == email)
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException("账号、用户名或邮箱已被注册")

    # 查找默认角色 "user"
    role_result = await db.execute(select(Role).where(Role.name == "user"))
    default_role = role_result.scalar_one_or_none()

    user = User(
        account=account,
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role_id=default_role.id if default_role else None,
    )
    db.add(user)
    await db.flush()
    # Eager-load role to avoid lazy-load error during serialization
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user.id)
    )
    return result.scalar_one()


async def login(db: AsyncSession, login_id: str, password: str) -> dict:
    """登录: 支持账号/用户名/邮箱, 返回 JWT 令牌对"""
    result = await db.execute(
        select(User).where(
            (User.account == login_id) | (User.username == login_id) | (User.email == login_id)
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.hashed_password):
        raise UnauthorizedException("用户名或密码错误")

    if not user.is_active:
        raise UnauthorizedException("账号已被禁用")

    # 更新最后登录时间
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    token_data = {"sub": str(user.id), "username": user.username}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
    }


async def refresh(db: AsyncSession, refresh_token: str) -> dict:
    """刷新令牌: 验证 refresh token, 返回新的令牌对"""
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise UnauthorizedException("无效的刷新令牌")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise UnauthorizedException("用户不存在或已禁用")

    token_data = {"sub": str(user.id), "username": user.username}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
    }


async def seed_default_roles(db: AsyncSession):
    """初始化默认角色 (应用启动时调用)"""
    defaults = [
        {
            "name": "admin",
            "description": "系统管理员",
            "permissions": {
                "can_login": True,
                "can_upload": True,
                "can_download": True,
                "can_modify": True,
                "can_delete": True,
                "can_manage_users": True,
                "can_manage_mounts": True,
                "can_manage_system": True,
            },
            "mount_permissions": {},
            "qos_limits": None,
        },
        {
            "name": "user",
            "description": "普通用户",
            "permissions": {
                "can_login": True,
                "can_upload": True,
                "can_download": True,
                "can_modify": True,
                "can_delete": False,
                "can_manage_users": False,
                "can_manage_mounts": False,
                "can_manage_system": False,
            },
            "mount_permissions": {},
            "qos_limits": {"max_download_kbps": 10240, "max_upload_kbps": 5120, "max_concurrent": 5},
        },
        {
            "name": "readonly",
            "description": "只读用户",
            "permissions": {
                "can_login": True,
                "can_upload": False,
                "can_download": True,
                "can_modify": False,
                "can_delete": False,
                "can_manage_users": False,
                "can_manage_mounts": False,
                "can_manage_system": False,
            },
            "mount_permissions": {},
            "qos_limits": {"max_download_kbps": 2048, "max_upload_kbps": 0, "max_concurrent": 2},
        },
    ]

    for role_data in defaults:
        result = await db.execute(select(Role).where(Role.name == role_data["name"]))
        if result.scalar_one_or_none() is None:
            db.add(Role(**role_data))

    await db.flush()


async def seed_admin_user(db: AsyncSession):
    """初始化默认管理员用户 — 首次启动时生成随机密码并输出到日志"""
    import os

    # 查找 admin 角色
    role_result = await db.execute(select(Role).where(Role.name == "admin"))
    admin_role = role_result.scalar_one_or_none()

    result = await db.execute(select(User).where(User.username == "admin"))
    admin = result.scalar_one_or_none()
    if admin is not None:
        # 已存在则确保角色为 admin
        if admin_role and admin.role_id != admin_role.id:
            admin.role_id = admin_role.id
            await db.flush()
        return

    # 优先使用环境变量 ADMIN_PASSWORD，否则生成随机密码
    password = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(16)

    admin = User(
        account="admin",
        username="admin",
        email="admin@multimount.local",
        hashed_password=hash_password(password),
        role_id=admin_role.id if admin_role else None,
    )
    db.add(admin)
    await db.flush()
    logger.warning("=" * 60)
    logger.warning("管理员账号已创建 — 用户名: admin, 密码: %s", password)
    logger.warning("请立即登录并修改密码！")
    logger.warning("=" * 60)
