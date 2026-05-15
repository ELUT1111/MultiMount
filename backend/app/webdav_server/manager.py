"""
WebDAV 服务生命周期管理 — 在独立线程中运行 wsgidav + cheroot 服务器。

支持:
  - 启动/停止服务
  - 热更新配置 (端口/SSL/根挂载点)
  - 状态查询
"""
from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import *  # noqa: F401,F403 — 触发适配器注册
from app.adapters.registry import AdapterRegistry
from app.core.security import decrypt_field
from app.models.mount import Mount
from app.webdav_server.domain_controller import UserDomainController
from app.webdav_server.provider import MultiMountDAVProvider

logger = logging.getLogger(__name__)


@dataclass
class WebDAVConfig:
    """WebDAV 服务配置"""
    host: str = "0.0.0.0"
    port: int = 8080
    ssl: bool = False
    ssl_cert_path: str = ""
    ssl_key_path: str = ""
    root_mount_id: int | None = None  # 指定根挂载点 (None = 显示所有)
    access_log: bool = True
    log_path: str = ""


@dataclass
class WebDAVStatus:
    """WebDAV 服务状态"""
    running: bool = False
    host: str = "0.0.0.0"
    port: int = 8080
    ssl: bool = False
    mount_count: int = 0
    error: str | None = None


class WebDAVManager:
    """WebDAV 服务管理器 — 单例模式"""

    _instance: "WebDAVManager | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._server_thread: threading.Thread | None = None
        self._server = None
        self._running = False
        self._config = WebDAVConfig()
        self._domain_controller: UserDomainController | None = None
        self._error: str | None = None

    @property
    def status(self) -> WebDAVStatus:
        return WebDAVStatus(
            running=self._running,
            host=self._config.host,
            port=self._config.port,
            ssl=self._config.ssl,
            mount_count=len(self._adapters) if hasattr(self, '_adapters') else 0,
            error=self._error,
        )

    async def start(self, db: AsyncSession, config: WebDAVConfig | None = None) -> WebDAVStatus:
        """启动 WebDAV 服务"""
        if self._running:
            return self.status

        if config:
            self._config = config

        try:
            # 构建挂载点 → 适配器映射
            self._adapters = await self._build_adapters(db)
            if not self._adapters:
                self._error = "没有可用的挂载点"
                return self.status

            # 创建 Provider 和 Domain Controller
            provider = MultiMountDAVProvider(self._adapters)
            self._domain_controller = UserDomainController()

            # 构造 wsgidav 配置
            wsgidav_config = self._build_wsgidav_config(provider)

            # 在独立线程中启动 cheroot 服务器
            self._server_thread = threading.Thread(
                target=self._run_server,
                args=(wsgidav_config,),
                daemon=True,
                name="webdav-server",
            )
            self._server_thread.start()
            self._running = True
            self._error = None
            logger.info(f"WebDAV 服务已启动: {self._config.host}:{self._config.port}")

        except Exception as e:
            self._error = str(e)
            self._running = False
            logger.error(f"WebDAV 服务启动失败: {e}")

        return self.status

    async def stop(self) -> WebDAVStatus:
        """停止 WebDAV 服务"""
        if not self._running:
            return self.status

        try:
            if self._server:
                self._server.stop()
            self._running = False
            self._error = None
            if self._domain_controller:
                self._domain_controller.close()
                self._domain_controller = None
            logger.info("WebDAV 服务已停止")
        except Exception as e:
            self._error = str(e)
            logger.error(f"WebDAV 服务停止失败: {e}")

        return self.status

    async def update_config(self, db: AsyncSession, config: WebDAVConfig) -> WebDAVStatus:
        """热更新配置 — 停止后重启"""
        was_running = self._running
        if was_running:
            await self.stop()
        self._config = config
        if was_running:
            return await self.start(db, config)
        return self.status

    async def _build_adapters(self, db: AsyncSession) -> dict[str, "BaseAdapter"]:
        """从数据库加载挂载点, 创建适配器实例"""
        adapters = {}
        # 仅加载在线或支持的挂载点
        result = await db.execute(select(Mount))
        mounts = result.scalars().all()

        for mount in mounts:
            try:
                # 解密配置中的敏感字段
                config = {}
                for k, v in (mount.config or {}).items():
                    if k in ("password", "access_key_secret", "private_key"):
                        try:
                            config[k] = decrypt_field(v)
                        except Exception:
                            config[k] = v
                    else:
                        config[k] = v

                adapter = AdapterRegistry.create(mount.type, config)
                # 使用挂载名称作为 WebDAV 路径段 (去除特殊字符)
                safe_name = mount.name.replace("/", "_").replace("\\", "_")
                adapters[safe_name] = adapter
            except Exception as e:
                logger.warning(f"挂载点 {mount.name} 加载失败: {e}")

        return adapters

    def _build_wsgidav_config(self, provider: MultiMountDAVProvider) -> dict:
        """构造 wsgidav 服务器配置"""
        config = {
            "host": self._config.host,
            "port": self._config.port,
            "provider_mapping": {"/": provider},
            "domaincontroller": self._domain_controller,
            "verbose": 1 if self._config.access_log else 0,
            "logging": {
                "enable": self._config.access_log,
                "verbose": 1,
            },
            # 禁用匿名访问
            "accept_anonymous": False,
            # 简化锁定 (WebDAV 锁定协议)
            "lock_manager": True,
            # 响应头
            "response_headers": {
                "Server": "MultiMount WebDAV",
            },
        }

        # SSL 配置
        if self._config.ssl and self._config.ssl_cert_path:
            config["ssl_certificate"] = self._config.ssl_cert_path
            config["ssl_private_key"] = self._config.ssl_key_path

        return config

    def _run_server(self, wsgidav_config: dict):
        """在独立线程中运行 WebDAV 服务器 (阻塞)"""
        try:
            from wsgidav.wsgidav_app import WsgiDAVApp
            from cheroot import wsgi as cheroot_wsgi

            app = WsgiDAVApp(wsgidav_config)

            self._server = cheroot_wsgi.Server(
                (wsgidav_config["host"], wsgidav_config["port"]),
                app,
            )

            # SSL 支持
            if "ssl_certificate" in wsgidav_config:
                self._server.ssl_adapter = _create_ssl_adapter(
                    wsgidav_config["ssl_certificate"],
                    wsgidav_config.get("ssl_private_key"),
                )

            self._server.start()

        except Exception as e:
            self._error = str(e)
            self._running = False
            logger.error(f"WebDAV 服务器线程异常: {e}")


def _create_ssl_adapter(cert_path: str, key_path: str | None):
    """创建 SSL 适配器 (用于 HTTPS)"""
    try:
        from cheroot.ssl.builtin import BuiltinSSLAdapter
        return BuiltinSSLAdapter(cert_path, key_path)
    except ImportError:
        logger.warning("SSL 适配器不可用, 将使用 HTTP")
        return None


# 全局单例
def get_webdav_manager() -> WebDAVManager:
    return WebDAVManager()
