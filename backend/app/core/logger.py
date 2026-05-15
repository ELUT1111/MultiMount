import logging
import sys
from pathlib import Path


def setup_logging(debug: bool = False):
    """配置结构化日志: 控制台 + 文件"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
    ]

    logging.basicConfig(level=level, format=fmt, handlers=handlers, force=True)

    # 降低第三方库日志级别
    for noisy in ("uvicorn", "sqlalchemy.engine", "paramiko", "botocore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger("multimount")
