from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Role(BaseModel):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 权限: {"can_login": true, "can_upload": true, "can_download": true, ...}
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    # 挂载点权限: {"mount_1": "read_write", "mount_2": "read_only", ...}
    mount_permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    # QoS: {"max_download_kbps": 1024, "max_upload_kbps": 512, "max_concurrent": 5}
    qos_limits: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 关联
    users = relationship("User", back_populates="role")

    def __repr__(self):
        return f"<Role {self.name}>"
