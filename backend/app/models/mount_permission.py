from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class MountPermission(BaseModel):
    __tablename__ = "mount_permissions_table"
    __table_args__ = (UniqueConstraint("mount_id", "user_id"),)

    mount_id: Mapped[int] = mapped_column(Integer, ForeignKey("mounts.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="read")  # "read" | "readwrite"
    granted_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    def __repr__(self):
        return f"<MountPermission mount={self.mount_id} user={self.user_id} level={self.level}>"
