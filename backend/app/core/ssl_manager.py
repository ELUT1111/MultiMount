"""
SSL/TLS 证书管理 — 证书上传、验证、存储、配置注入。

证书文件存储在 data/certs/ 目录下, 配置信息持久化到 data/ssl_config.json。
"""
import json
import logging
import ssl
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("multimount.ssl")

CERTS_DIR = Path("data/certs")
CONFIG_FILE = Path("data/ssl_config.json")


@dataclass
class SSLConfig:
    """SSL 配置状态"""
    cert_path: str = ""
    key_path: str = ""
    force_https: bool = False
    auto_redirect: bool = True
    cert_expiry: str = ""
    cert_valid: bool = False


def _ensure_dirs():
    CERTS_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> SSLConfig:
    """从磁盘加载 SSL 配置"""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return SSLConfig(**data)
        except (json.JSONDecodeError, TypeError):
            pass
    return SSLConfig()


def save_config(config: SSLConfig):
    """持久化 SSL 配置到磁盘"""
    _ensure_dirs()
    CONFIG_FILE.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")


def validate_cert(cert_path: str) -> dict:
    """
    验证证书文件有效性。
    返回 {"valid": bool, "expiry": str, "error": str | None}
    """
    path = Path(cert_path)
    if not path.exists():
        return {"valid": False, "expiry": "", "error": "证书文件不存在"}

    try:
        # 使用 Python ssl 模块解析证书
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(cert_path)

        # 通过 OpenSSL 读取过期时间
        import subprocess
        result = subprocess.run(
            ["openssl", "x509", "-in", cert_path, "-noout", "-enddate"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            # 输出格式: notAfter=May 15 12:00:00 2026 GMT
            date_str = result.stdout.strip().split("=", 1)[1]
            expiry = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
            expiry = expiry.replace(tzinfo=timezone.utc)
            return {
                "valid": expiry > datetime.now(timezone.utc),
                "expiry": expiry.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "error": None,
            }
    except FileNotFoundError:
        # openssl 不可用, 尝试基础检查
        content = path.read_text()
        if "BEGIN CERTIFICATE" in content:
            return {"valid": True, "expiry": "未知 (openssl 不可用)", "error": None}
    except Exception as e:
        logger.warning("证书验证失败: %s", e)

    return {"valid": False, "expiry": "", "error": "证书格式无效"}


def save_cert_file(filename: str, content: bytes) -> str:
    """保存上传的证书/私钥文件, 返回保存路径"""
    _ensure_dirs()
    # 安全文件名: 仅保留基本名称
    safe_name = Path(filename).name
    dest = CERTS_DIR / safe_name
    dest.write_bytes(content)
    logger.info("证书文件已保存: %s", dest)
    return str(dest)


def get_ssl_context() -> ssl.SSLContext | None:
    """
    根据当前配置创建 SSL 上下文, 用于 Uvicorn SSL 启动。
    如果证书未配置或无效, 返回 None。
    """
    config = load_config()
    if not config.cert_valid or not config.cert_path or not config.key_path:
        return None

    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(config.cert_path, config.key_path)
        return ctx
    except Exception as e:
        logger.error("创建 SSL 上下文失败: %s", e)
        return None
