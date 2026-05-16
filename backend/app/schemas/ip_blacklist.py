# IP 黑名单请求/响应 Schema
from pydantic import BaseModel
from datetime import datetime


class IPBlacklistCreate(BaseModel):
    """添加 IP 到黑名单"""
    ip_address: str
    reason: str | None = None


class IPBlacklistOut(BaseModel):
    """IP 黑名单条目输出"""
    id: int
    ip_address: str
    reason: str | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
