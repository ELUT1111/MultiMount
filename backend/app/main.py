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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期: 启动时初始化数据库和目录"""
    logger = setup_logging(debug=settings.DEBUG)
    logger.info("MultiMount 正在启动...")

    # 确保数据目录存在
    Path("data").mkdir(exist_ok=True)
    Path("certs").mkdir(exist_ok=True)

    # 初始化数据库表
    await init_db()
    logger.info("数据库初始化完成")

    # 初始化默认角色和管理员用户
    from app.services.auth_service import seed_default_roles, seed_admin_user
    from app.database import async_session_factory

    async with async_session_factory() as db:
        await seed_default_roles(db)
        await seed_admin_user(db)
        await db.commit()
    logger.info("默认角色和管理员用户初始化完成")

    yield

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
