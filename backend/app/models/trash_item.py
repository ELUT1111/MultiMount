from datetime import datetime

from sqlalchemy import Boolean, BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class TrashItem(BaseModel):
    __tablename__ = "trash_items"

    mount_id: Mapped[int] = mapped_column(Integer, ForeignKey("mounts.id"), nullable=False, index=True)
    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    trash_path: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_dir: Mapped[bool] = mapped_column(Boolean, default=False)
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    deleted_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    deleted_by_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
