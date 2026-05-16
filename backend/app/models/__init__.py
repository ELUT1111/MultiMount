# 导入所有模型, 确保 SQLAlchemy metadata 注册完整 (Alembic 迁移需要)
from app.models.user import User  # noqa: F401
from app.models.role import Role  # noqa: F401
from app.models.mount import Mount  # noqa: F401
from app.models.transfer_task import TransferTask  # noqa: F401
from app.models.share_link import ShareLink  # noqa: F401
from app.models.ip_blacklist import IPBlacklist  # noqa: F401
from app.models.access_log import AccessLog  # noqa: F401
