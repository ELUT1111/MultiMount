import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logger import setup_logging
from app.core.middleware import register_middleware
from app.database import init_db

settings = get_settings()


async def _search_index_refresh_loop(logger) -> None:
    from app.database import async_session_factory
    from app.services.search_service import refresh_all_indexes

    while True:
        await asyncio.sleep(settings.SEARCH_INDEX_REFRESH_INTERVAL_SECONDS)
        try:
            async with async_session_factory() as db:
                summary = await refresh_all_indexes(db)
            logger.info("搜索索引定时刷新完成: %s", summary)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("搜索索引定时刷新失败: %s", exc)


def _validate_security_config() -> None:
    """阻止生产环境使用不安全的默认配置。"""
    default_jwt_secrets = {
        "CHANGE_ME_TO_A_RANDOM_SECRET_KEY",
        "multimount-dev-secret-key-change-in-production",
    }
    errors = []
    if settings.JWT_SECRET_KEY in default_jwt_secrets:
        errors.append("JWT_SECRET_KEY 不能使用默认值")
    if not settings.ENCRYPTION_KEY:
        errors.append("ENCRYPTION_KEY 必须设置为固定密钥")

    if errors and not settings.DEBUG:
        raise RuntimeError("生产配置不安全: " + "; ".join(errors))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期: 启动时初始化数据库和目录"""
    logger = setup_logging(debug=settings.DEBUG)
    logger.info("MultiMount 正在启动...")
    _validate_security_config()

    # 确保数据目录存在
    Path("data").mkdir(exist_ok=True)
    Path("certs").mkdir(exist_ok=True)

    # 初始化数据库表
    await init_db()
    logger.info("数据库初始化完成")

    # 初始化默认角色和管理员用户
    from app.services.auth_service import seed_default_roles, seed_admin_user
    from app.services.ip_blacklist_service import init_cache
    from app.services.transfer_service import recover_unfinished_tasks
    from app.database import async_session_factory

    async with async_session_factory() as db:
        await seed_default_roles(db)
        await seed_admin_user(db)
        await db.commit()
        await init_cache(db)
    logger.info("默认角色和管理员用户初始化完成")

    recovered = await recover_unfinished_tasks()
    if recovered:
        logger.info("已恢复 %d 个未完成传输任务", recovered)

    search_index_task = asyncio.create_task(_search_index_refresh_loop(logger))

    # 安全警告
    if settings.JWT_SECRET_KEY in ("CHANGE_ME_TO_A_RANDOM_SECRET_KEY", "multimount-dev-secret-key-change-in-production"):
        logger.warning("⚠ JWT_SECRET_KEY 使用默认值, 请在 .env 中设置随机密钥!")
    if not settings.ENCRYPTION_KEY:
        logger.warning("⚠ ENCRYPTION_KEY 为空, 每次重启后已加密数据将无法解密! 请在 .env 中设置固定密钥")
    if settings.DEBUG:
        logger.warning("⚠ DEBUG=True, 生产环境请设置 DEBUG=False")

    try:
        yield
    finally:
        search_index_task.cancel()
        try:
            await search_index_task
        except asyncio.CancelledError:
            pass

    logger.info("MultiMount 正在关闭...")


app = FastAPI(
    title=settings.APP_NAME,
    description="多协议统一文件挂载管理平台",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 自定义中间件 & 异常处理器
register_middleware(app)
register_exception_handlers(app)

# 静态文件 (生产环境下前端构建产物)
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# 注册 API 路由
from app.api.router import api_router  # noqa: E402

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME}
