from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "MultiMount"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/multimount.db"

    # JWT
    JWT_SECRET_KEY: str = "CHANGE_ME_TO_A_RANDOM_SECRET_KEY"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Fernet 加密密钥 (用于加密挂载配置中的密码等敏感字段)
    ENCRYPTION_KEY: str = ""

    # Transfer QoS
    TRANSFER_MAX_CONCURRENT_GLOBAL: int = 4
    TRANSFER_MAX_CONCURRENT_PER_USER: int = 2
    TRANSFER_MAX_CONCURRENT_PER_MOUNT: int = 2
    TRANSFER_DEFAULT_DOWNLOAD_LIMIT_KBPS: int = 0
    TRANSFER_DEFAULT_UPLOAD_LIMIT_KBPS: int = 0

    # Search and preview
    SEARCH_INDEX_REFRESH_INTERVAL_SECONDS: int = 3600

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
