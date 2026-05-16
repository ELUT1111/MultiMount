from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Mount(BaseModel):
    __tablename__ = "mounts"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # local/ftp/sftp/webdav/oss/s3
    status: Mapped[str] = mapped_column(String(16), default="offline")  # online/connecting/offline

    # 创建者 (None 表示系统预置)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者 ID")

    # 协议专属配置 (敏感字段加密存储)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # 高级配置: {"cache_ttl": 300, "timeout": 30, "auto_reconnect": true}
    advanced_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    capacity_used: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    capacity_total: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_connected_at = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Mount {self.name} ({self.type})>"
