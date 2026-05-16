# IP 黑名单模型 — 用于中间件层拦截恶意 IP
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IPBlacklist(BaseModel):
    """IP 黑名单条目"""
    __tablename__ = "ip_blacklist"

    ip_address: Mapped[str] = mapped_column(String(45), unique=True, index=True, comment="IPv4/IPv6 地址")
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="拉黑原因")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否生效")
