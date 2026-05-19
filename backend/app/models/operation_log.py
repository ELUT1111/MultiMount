from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class OperationLog(BaseModel):
    """业务操作审计日志。"""

    __tablename__ = "operation_logs"

    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, default="file")
    mount_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("mounts.id"), nullable=True, index=True)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success", index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
