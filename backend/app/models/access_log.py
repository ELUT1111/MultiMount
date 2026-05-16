# 访问日志模型 — 由中间件异步写入，供请求监控页面查询
from sqlalchemy import String, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AccessLog(BaseModel):
    """HTTP 访问日志"""
    __tablename__ = "access_logs"

    ip_address: Mapped[str] = mapped_column(String(45), index=True, comment="客户端 IP")
    method: Mapped[str] = mapped_column(String(10), comment="HTTP 方法")
    path: Mapped[str] = mapped_column(String(512), index=True, comment="请求路径")
    status_code: Mapped[int] = mapped_column(Integer, comment="响应状态码")
    response_time_ms: Mapped[float] = mapped_column(Float, comment="响应耗时 (ms)")
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="User-Agent")
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, comment="登录用户 ID")
