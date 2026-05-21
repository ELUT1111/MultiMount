from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class FileIndex(BaseModel):
    __tablename__ = "file_indexes"

    mount_id: Mapped[int] = mapped_column(ForeignKey("mounts.id"), nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    mount_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    mount_owner: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    parent_path: Mapped[str] = mapped_column(Text, nullable=False, default="/")
    is_dir: Mapped[bool] = mapped_column(Boolean, default=False)
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extension: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    file_type: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    file_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("mount_id", "path", name="uq_file_indexes_mount_path"),
        Index("ix_file_indexes_mount_type", "mount_id", "file_type"),
        Index("ix_file_indexes_size", "size"),
        Index("ix_file_indexes_modified_at", "modified_at"),
    )
