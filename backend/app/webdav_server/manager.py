from __future__ import annotations

import logging
import ssl
import threading
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.webdav_server.domain_controller import UserDomainController
from app.webdav_server.middleware import AccessLogMiddleware
from app.webdav_server.provider import MultiMountDAVProvider

logger = logging.getLogger(__name__)


@dataclass
class WebDAVConfig:
    # WebDAV 服务运行配置，由系统设置面板保存/传入。
    # root_mount_id 不为空时，只暴露指定挂载点；为空时根目录列出所有可见挂载。
    host: str = "0.0.0.0"
    port: int = 8080
    ssl: bool = False
    ssl_cert_path: str = ""
    ssl_key_path: str = ""
    root_mount_id: int | None = None
    access_log: bool = True
    log_path: str = ""
    recycle_delete: bool = True


@dataclass
class WebDAVStatus:
    # 返回给前端的运行状态快照，不直接暴露 cheroot Server 对象。
    running: bool = False
    host: str = "0.0.0.0"
    port: int = 8080
    ssl: bool = False
    ssl_cert_path: str = ""
    ssl_key_path: str = ""
    mount_count: int = 0
    error: str | None = None
    recycle_delete: bool = True
    root_mount_id: int | None = None
    access_log: bool = True
    log_path: str = ""


class WebDAVManager:
    # WebDAV 服务在进程内只能有一个监听实例，因此管理器实现为单例。
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
        # cheroot Server 是同步阻塞服务，必须放在独立线程中运行。
        self._server_thread: threading.Thread | None = None
        self._server = None
        self._running = False
        self._startup_event = threading.Event()
        self._config = WebDAVConfig()
        self._domain_controller: UserDomainController | None = None
        self._error: str | None = None
        self._mount_count = 0

    @property
    def status(self) -> WebDAVStatus:
        return WebDAVStatus(
            running=self._running,
            host=self._config.host,
            port=self._config.port,
            ssl=self._config.ssl,
            ssl_cert_path=self._config.ssl_cert_path,
            ssl_key_path=self._config.ssl_key_path,
            mount_count=self._mount_count,
            error=self._error,
            recycle_delete=self._config.recycle_delete,
            root_mount_id=self._config.root_mount_id,
            access_log=self._config.access_log,
            log_path=self._config.log_path,
        )

    async def start(self, db: AsyncSession, config: WebDAVConfig | None = None) -> WebDAVStatus:
        if self._running:
            # 重复启动直接返回当前状态，避免重复绑定端口。
            return self.status

        if config:
            self._config = config

        try:
            # Provider 负责把 WebDAV 路径映射到 MountHub 挂载适配器。
            provider = MultiMountDAVProvider(
                async_session_factory,
                recycle_delete=self._config.recycle_delete,
                root_mount_id=self._config.root_mount_id,
            )
            wsgidav_config = self._build_wsgidav_config(provider)

            self._server_thread = threading.Thread(
                target=self._run_server,
                args=(wsgidav_config,),
                daemon=True,
                name="webdav-server",
            )
            self._startup_event.clear()
            self._server_thread.start()

            # WebDAV 服务在独立线程中启动；这里等待线程明确成功/失败，避免 UI 显示假运行。
            if not self._startup_event.wait(timeout=3):
                self._error = self._error or "WebDAV 服务启动超时"
                self._running = False
                logger.error("WebDAV service failed to start: %s", self._error)
                return self.status

            if not self._running:
                logger.error("WebDAV service failed to start: %s", self._error)
                return self.status

            self._mount_count = await self._count_served_mounts(db)
            logger.info("WebDAV service started on %s:%s", self._config.host, self._config.port)
        except Exception as exc:
            self._error = str(exc)
            self._running = False
            logger.error("WebDAV service failed to start: %s", exc)

        return self.status

    async def stop(self) -> WebDAVStatus:
        if not self._running:
            return self.status

        try:
            if self._server:
                # stop 会让 cheroot.start() 退出，随后服务线程自然结束。
                self._server.stop()
            self._running = False
            self._error = None
            if self._domain_controller:
                self._domain_controller.close()
                self._domain_controller = None
            self._mount_count = 0
            logger.info("WebDAV service stopped")
        except Exception as exc:
            self._error = str(exc)
            logger.error("WebDAV service failed to stop: %s", exc)

        return self.status

    async def update_config(self, db: AsyncSession, config: WebDAVConfig) -> WebDAVStatus:
        was_running = self._running
        if was_running:
            await self.stop()
        self._config = config
        if was_running:
            # 配置更新采用停再启，保证端口、SSL、根挂载等 cheroot 级配置真正生效。
            return await self.start(db, config)
        return self.status

    def _build_wsgidav_config(self, provider: MultiMountDAVProvider) -> dict:
        config = {
            "host": self._config.host,
            "port": self._config.port,
            # 所有 WebDAV 请求先进入根 provider，再由 provider 解析挂载名和内部路径。
            "provider_mapping": {"/": provider},
            "http_authenticator": {
                "domain_controller": UserDomainController,
                # Windows 资源管理器对 Basic Auth 兼容性最好；Digest 当前未启用。
                "accept_basic": True,
                "accept_digest": False,
                "default_to_digest": False,
            },
            "verbose": 1 if self._config.access_log else 0,
            "logging": {
                "enable": self._config.access_log,
            },
            "accept_anonymous": False,
            # True 表示使用 WsgiDAV 默认锁存储，支持 Windows 客户端的 LOCK/UNLOCK 请求。
            "lock_storage": True,
        }

        if self._config.ssl and self._config.ssl_cert_path:
            # WebDAV TLS 独立于 FastAPI/uvicorn HTTPS；两者需要分别配置证书。
            config["ssl_certificate"] = self._config.ssl_cert_path
            config["ssl_private_key"] = self._config.ssl_key_path

        return config

    async def _count_served_mounts(self, db: AsyncSession) -> int:
        from sqlalchemy import func, select
        from app.models.mount import Mount

        query = select(func.count(Mount.id))
        if self._config.root_mount_id is not None:
            query = query.where(Mount.id == self._config.root_mount_id)
        result = await db.execute(query)
        return int(result.scalar() or 0)

    def _run_server(self, wsgidav_config: dict):
        try:
            from cheroot import wsgi as cheroot_wsgi
            from wsgidav.wsgidav_app import WsgiDAVApp

            # WsgiDAVApp 是标准 WSGI 应用，cheroot 负责实际 socket 监听。
            app = WsgiDAVApp(wsgidav_config)
            if app.http_authenticator:
                self._domain_controller = app.http_authenticator.get_domain_controller()
            if self._config.access_log:
                app = AccessLogMiddleware(app, self._config.log_path)
            self._server = cheroot_wsgi.Server(
                (wsgidav_config["host"], wsgidav_config["port"]),
                app,
            )

            if "ssl_certificate" in wsgidav_config:
                self._server.ssl_adapter = _create_ssl_adapter(
                    wsgidav_config["ssl_certificate"],
                    wsgidav_config.get("ssl_private_key"),
                )

            self._running = True
            self._error = None
            self._startup_event.set()
            self._server.start()
        except Exception as exc:
            self._error = str(exc)
            self._running = False
            self._startup_event.set()
            logger.error("WebDAV server thread failed: %s", exc)


def _create_ssl_adapter(cert_path: str, key_path: str | None):
    try:
        from cheroot.ssl.builtin import BuiltinSSLAdapter
        adapter = BuiltinSSLAdapter(cert_path, key_path)
        # WebDAV HTTPS 只使用服务端证书，不要求 Windows 客户端选择个人证书。
        adapter.context.verify_mode = ssl.CERT_NONE
        adapter.context.check_hostname = False
        return adapter
    except ImportError:
        logger.warning("Cheroot SSL adapter is unavailable; WebDAV will keep using HTTP")
        return None


def get_webdav_manager() -> WebDAVManager:
    return WebDAVManager()
