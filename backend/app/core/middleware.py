import time
import logging
import asyncio
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.services.ip_blacklist_service import is_blocked

logger = logging.getLogger("multimount.access")


# ── IP 黑名单拦截中间件 ──────────────────────────────────────

class IPBlacklistMiddleware(BaseHTTPMiddleware):
    """拦截被拉黑的 IP，返回 403。黑名单通过内存 set 判断，无 DB 开销。"""

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        if is_blocked(client_ip):
            logger.warning("已拦截黑名单 IP: %s %s", client_ip, request.url.path)
            return JSONResponse(status_code=403, content={"detail": "IP 已被封禁"})
        return await call_next(request)


# ── 请求日志 + 访问记录中间件 ────────────────────────────────

async def _write_access_log(ip, method, path, status, elapsed_ms, user_agent, user_id):
    """异步写入访问日志到数据库，不阻塞主请求"""
    try:
        from app.database import async_session_factory
        from app.models.access_log import AccessLog
        async with async_session_factory() as db:
            db.add(AccessLog(
                ip_address=ip,
                method=method,
                path=path,
                status_code=status,
                response_time_ms=round(elapsed_ms, 1),
                user_agent=user_agent[:512] if user_agent else None,
                user_id=user_id,
            ))
            await db.commit()
    except Exception:
        logger.debug("写入访问日志失败", exc_info=True)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """记录每个请求的方法、路径、状态码和耗时，并异步写入 AccessLog 表"""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "%s %s → %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        # 异步写入访问日志（跳过健康检查等高频无意义路径）
        path = request.url.path
        if not path.startswith("/health"):
            asyncio.create_task(_write_access_log(
                ip=request.client.host if request.client else "unknown",
                method=request.method,
                path=path,
                status=response.status_code,
                elapsed_ms=elapsed_ms,
                user_agent=request.headers.get("user-agent"),
                user_id=None,  # 简化: 不在中间件层解析 JWT
            ))

        return response


def register_middleware(app: FastAPI):
    """注册所有自定义中间件 (后注册的先执行)"""
    # 1. 请求日志 (最后注册 → 最先执行: 记录所有请求)
    app.add_middleware(RequestLoggingMiddleware)
    # 2. IP 黑名单 (先注册 → 后执行: 但黑名单检查应在日志之前拦截)
    #    实际上 BaseHTTPMiddleware 按注册顺序执行, 所以先注册的先执行
    app.add_middleware(IPBlacklistMiddleware)
