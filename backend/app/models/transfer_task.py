"""Transfer task records for queued copy/move jobs."""

from sqlalchemy import BigInteger, ForeignKey, Integer, JSON, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class TransferTask(BaseModel):
    __tablename__ = "transfer_tasks"

    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # Task type: copy / move
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Task status: pending / running / paused / completed / failed
    status: Mapped[str] = mapped_column(String(16), default="pending")

    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    target_path: Mapped[str] = mapped_column(Text, nullable=False)
    mount_id: Mapped[int | None] = mapped_column(ForeignKey("mounts.id"), nullable=True)
    source_mount_id: Mapped[int | None] = mapped_column(ForeignKey("mounts.id"), nullable=True)
    target_mount_id: Mapped[int | None] = mapped_column(ForeignKey("mounts.id"), nullable=True)
    conflict_policy: Mapped[str] = mapped_column(String(16), default="error")

    transferred: Mapped[int] = mapped_column(BigInteger, default=0)
    chunk_size: Mapped[int] = mapped_column(Integer, default=65536)
    speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    download_limit_bps: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    upload_limit_bps: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checkpoint: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return f"<TransferTask {self.id} {self.type} {self.file_name} {self.status}>"
