from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Notification(BaseModel):
    __tablename__ = "notifications"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="接收者 ID")
    type: Mapped[str] = mapped_column(String(64), nullable=False, comment="通知类型")
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="通知标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="通知内容")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已读")
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="关联 ID (挂载/角色)")

    def __repr__(self):
        return f"<Notification {self.type} → user={self.user_id}>"
