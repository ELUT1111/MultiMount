# IP 黑名单请求/响应 Schema
from pydantic import BaseModel
from pydantic import field_serializer
from datetime import datetime

from app.utils.datetime_utils import iso_utc


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

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime):
        return iso_utc(value)

    class Config:
        from_attributes = True
