"""
分享链接模型 — 生成带令牌的文件分享链接, 支持过期时间和访问次数限制。
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ShareLink(BaseModel):
    __tablename__ = "share_links"

    # 关联的挂载点和文件路径
    mount_id: Mapped[int] = mapped_column(ForeignKey("mounts.id"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_dir: Mapped[bool] = mapped_column(Boolean, default=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 本地快照信息。老数据可能为空, 访问时会回退到原挂载路径。
    snapshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_size: Mapped[int] = mapped_column(BigInteger, default=0)

    # 分享令牌 (URL 中使用的唯一标识)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # 创建者
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # 过期时间 (NULL 表示永不过期)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 最大访问次数 (0 表示不限制)
    max_views: Mapped[int] = mapped_column(Integer, default=0)
    # 当前已访问次数
    view_count: Mapped[int] = mapped_column(Integer, default=0)

    # 是否启用
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 提取码 (可选, 空表示无需提取码)
    access_code: Mapped[str | None] = mapped_column(String(128), nullable=True)

    def __repr__(self):
        return f"<ShareLink {self.token}>"
