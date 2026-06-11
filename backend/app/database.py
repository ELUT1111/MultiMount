from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

# 全局异步会话工厂。expire_on_commit=False 可以避免提交后 ORM 对象属性被清空，
# 便于 API 层在事务提交后继续序列化响应对象。
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """创建所有表 (开发用, 生产应使用 Alembic)"""
    import sqlalchemy as sa
    import app.models  # noqa: F401 - ensure all models are registered

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 这里保留轻量级“补列”逻辑，便于旧 SQLite 数据库随版本启动时自动追平。
        # 生产环境若接入正式数据库，仍应优先使用 Alembic 迁移来管理表结构。
        # 增量迁移: 为 notifications 表添加 metadata 列 (如不存在)
        try:
            await conn.execute(sa.text("ALTER TABLE notifications ADD COLUMN metadata JSON"))
        except Exception:
            pass  # 列已存在则忽略
        try:
            await conn.execute(sa.text("ALTER TABLE notifications ADD COLUMN is_archived BOOLEAN DEFAULT 0"))
        except Exception:
            pass  # 列已存在则忽略

        # 增量迁移: 为 transfer_tasks 增加跨挂载传输与冲突策略字段
        transfer_columns = [
            ("source_mount_id", "INTEGER"),
            ("target_mount_id", "INTEGER"),
            ("conflict_policy", "VARCHAR(16) DEFAULT 'error'"),
            ("download_limit_bps", "BIGINT"),
            ("upload_limit_bps", "BIGINT"),
            ("checkpoint", "JSON"),
        ]
        for column_name, column_type in transfer_columns:
            try:
                await conn.execute(sa.text(f"ALTER TABLE transfer_tasks ADD COLUMN {column_name} {column_type}"))
            except Exception:
                pass
        # 增量迁移: 为 share_links 增加快照元数据字段
        share_columns = [
            ("file_name", "VARCHAR(512)"),
            ("is_dir", "BOOLEAN DEFAULT 0"),
            ("file_size", "BIGINT DEFAULT 0"),
            ("mime_type", "VARCHAR(255)"),
            ("snapshot_path", "TEXT"),
            ("snapshot_size", "BIGINT DEFAULT 0"),
        ]
        for column_name, column_type in share_columns:
            try:
                await conn.execute(sa.text(f"ALTER TABLE share_links ADD COLUMN {column_name} {column_type}"))
            except Exception:
                pass
        # 增量迁移: 为 users 表添加 account 列 (如不存在)
        try:
            await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_file_indexes_mount_type ON file_indexes(mount_id, file_type)"))
            await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_file_indexes_size ON file_indexes(size)"))
            await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_file_indexes_modified_at ON file_indexes(modified_at)"))
        except Exception:
            pass
        try:
            await conn.execute(sa.text("ALTER TABLE users ADD COLUMN account VARCHAR(64)"))
            # 回填已有用户的 account (默认使用 username)
            await conn.execute(sa.text("UPDATE users SET account = username WHERE account IS NULL"))
            # 创建唯一索引
            try:
                await conn.execute(sa.text("CREATE UNIQUE INDEX ix_users_account ON users(account)"))
            except Exception:
                pass
        except Exception:
            pass  # 列已存在则忽略


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入: 获取数据库会话"""
    from app.services import notification_service

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
            # WebSocket 推送要等数据库提交成功后再发送，避免前端收到实际未落库的消息。
            await notification_service.flush_queued_pushes(session)
        except Exception:
            await session.rollback()
            notification_service.clear_queued_pushes(session)
            raise
        finally:
            await session.close()
