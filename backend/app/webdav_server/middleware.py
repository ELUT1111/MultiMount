"""
WebDAV 中间件 — 访问日志记录。

在 wsgidav 请求处理前后注入日志, 记录:
  - 客户端 IP / 用户名
  - 请求方法 (GET/PUT/DELETE/PROPFIND 等)
  - 请求路径
  - 响应状态码
  - 耗时
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger("webdav.access")


class AccessLogMiddleware:
    """
    WebDAV 访问日志中间件 — 包装 WSGI 应用, 记录每次请求。

    用法:
        app = WsgiDAVApp(config)
        app = AccessLogMiddleware(app)
    """

    def __init__(self, app):
        self._app = app

    def __call__(self, environ, start_response):
        """WSGI 入口"""
        start_time = time.time()

        # 提取请求信息
        method = environ.get("REQUEST_METHOD", "UNKNOWN")
        path = environ.get("PATH_INFO", "/")
        remote_addr = environ.get("REMOTE_ADDR", "-")
        # wsgidav 认证后会在 environ 中设置 REMOTE_USER
        username = environ.get("REMOTE_USER", "-")

        # 包装 start_response 以捕获状态码
        status_code = [None]

        def _start_response(status, headers, exc_info=None):
            status_code[0] = status.split(" ")[0] if status else "???"
            return start_response(status, headers, exc_info)

        try:
            result = self._app(environ, _start_response)
            return result
        finally:
            elapsed = time.time() - start_time
            logger.info(
                f"{remote_addr} [{username}] {method} {path} "
                f"→ {status_code[0]} ({elapsed:.3f}s)"
            )
