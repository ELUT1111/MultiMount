"""
WebDAV 域控制器 — 实现 wsgidav 的域认证接口, 复用 User 模型进行 Basic Auth。

WebDAV 客户端 (Windows Explorer / macOS Finder) 使用 HTTP Basic Auth 发送凭证,
本控制器验证用户名密码是否与数据库中的用户匹配。
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.core.security import verify_password

if TYPE_CHECKING:
    from wsgidav.request_server import RequestServer


def _run_async(coro):
    """在同步上下文中运行异步协程"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class UserDomainController:
    """
    基于数据库用户的域控制器。

    wsgidav 通过此接口验证 WebDAV 客户端的 Basic Auth 凭证。
    """

    def __init__(self):
        settings = get_settings()
        self._engine = create_async_engine(settings.DATABASE_URL)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def _verify_user(self, username: str, password: str) -> bool:
        """异步验证用户名密码"""
        from app.models.user import User

        async with self._session_factory() as db:
            result = await db.execute(
                select(User).where(User.username == username, User.is_active == True)
            )
            user = result.scalar_one_or_none()
            if user is None:
                return False
            return verify_password(password, user.hashed_password)

    def get_domain_realm_name(self) -> str:
        """返回域名称 (显示在认证对话框中)"""
        return "MultiMount WebDAV"

    def require_authentication(self, realm: str, environ: dict) -> bool:
        """是否需要认证 (总是需要)"""
        return True

    def is_realm_user(self, realm: str, username: str, environ: dict) -> bool:
        """检查用户是否存在于该域中"""
        from app.models.user import User

        async def _check():
            async with self._session_factory() as db:
                result = await db.execute(
                    select(User).where(User.username == username, User.is_active == True)
                )
                return result.scalar_one_or_none() is not None

        try:
            return _run_async(_check())
        except Exception:
            return False

    def basic_auth_user(self, realm: str, username: str, password: str,
                        environ: dict) -> bool:
        """验证 Basic Auth 凭证 — wsgidav 核心认证回调"""
        try:
            return _run_async(self._verify_user(username, password))
        except Exception:
            return False

    def supports_http_digest_auth(self) -> bool:
        """不支持 Digest Auth, 仅使用 Basic Auth"""
        return False

    def close(self):
        """清理资源"""
        _run_async(self._engine.dispose())
