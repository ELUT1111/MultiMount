"""
系统设置服务 — HTTPS 配置、日志管理、系统信息查询。
"""
import logging
import shutil
from datetime import datetime
from pathlib import Path

from app.core.ssl_manager import (
    SSLConfig, load_config, save_config, validate_cert, save_cert_file,
)

logger = logging.getLogger("multimount.system")

LOGS_DIR = Path("logs")


# ── HTTPS 配置 ─────────────────────────────────────────────

def get_https_status() -> dict:
    """获取当前 HTTPS 配置状态"""
    config = load_config()
    return {
        "cert_valid": config.cert_valid,
        "cert_expiry": config.cert_expiry,
        "force_https": config.force_https,
        "auto_redirect": config.auto_redirect,
        "cert_path": config.cert_path,
        "key_path": config.key_path,
    }


def upload_certificate(cert_content: bytes, cert_filename: str) -> dict:
    """上传并验证 SSL 证书"""
    saved_path = save_cert_file(cert_filename, cert_content)
    result = validate_cert(saved_path)

    config = load_config()
    config.cert_path = saved_path
    config.cert_valid = result["valid"]
    config.cert_expiry = result["expiry"]
    save_config(config)

    logger.info("证书已上传: %s, 有效: %s", saved_path, result["valid"])
    return {"path": saved_path, "valid": result["valid"], "expiry": result["expiry"], "error": result.get("error")}


def upload_key(key_content: bytes, key_filename: str) -> dict:
    """上传 SSL 私钥文件"""
    saved_path = save_cert_file(key_filename, key_content)

    config = load_config()
    config.key_path = saved_path
    save_config(config)

    logger.info("私钥已上传: %s", saved_path)
    return {"path": saved_path}


def update_https_config(force_https: bool | None = None, auto_redirect: bool | None = None) -> dict:
    """更新 HTTPS 配置选项"""
    config = load_config()
    if force_https is not None:
        config.force_https = force_https
    if auto_redirect is not None:
        config.auto_redirect = auto_redirect
    save_config(config)
    logger.info("HTTPS 配置已更新: force_https=%s, auto_redirect=%s", config.force_https, config.auto_redirect)
    return get_https_status()


# ── 日志管理 ───────────────────────────────────────────────

def list_logs(log_type: str = "system", start_date: str = "", end_date: str = "") -> list[dict]:
    """
    读取日志条目。
    log_type: system | access | transfer
    """
    log_file = LOGS_DIR / f"{log_type}.log"
    if not log_file.exists():
        # 回退到 app.log (系统日志)
        if log_type == "system":
            log_file = LOGS_DIR / "app.log"
        if not log_file.exists():
            return []

    entries = []
    try:
        for line in log_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            entry = _parse_log_line(line)
            # 日期过滤
            if start_date and entry["timestamp"] < start_date:
                continue
            if end_date and entry["timestamp"] > end_date + " 23:59:59":
                continue
            entries.append(entry)
    except Exception as e:
        logger.error("读取日志失败: %s", e)

    # 最新在前, 限制 500 条
    return entries[-500:][::-1]


def _parse_log_line(line: str) -> dict:
    """解析单行日志, 提取时间戳/级别/消息/来源"""
    # 格式: "2026-05-15 10:30:00 | INFO     | multimount | 消息内容"
    parts = line.split(" | ", 3)
    if len(parts) >= 4:
        return {
            "timestamp": parts[0].strip(),
            "level": parts[1].strip(),
            "source": parts[2].strip(),
            "message": parts[3].strip(),
        }
    return {"timestamp": "", "level": "INFO", "source": "system", "message": line}


def export_logs(log_type: str = "system") -> str | None:
    """导出日志文件, 返回文件路径"""
    log_file = LOGS_DIR / f"{log_type}.log"
    if not log_file.exists() and log_type == "system":
        log_file = LOGS_DIR / "app.log"
    if not log_file.exists():
        return None

    export_dir = Path("data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = export_dir / f"{log_type}_{timestamp}.log"
    shutil.copy2(log_file, export_path)
    logger.info("日志已导出: %s", export_path)
    return str(export_path)


def clear_logs(log_type: str = "system") -> bool:
    """清空指定类型的日志"""
    log_file = LOGS_DIR / f"{log_type}.log"
    if not log_file.exists() and log_type == "system":
        log_file = LOGS_DIR / "app.log"
    if not log_file.exists():
        return False

    log_file.write_text("", encoding="utf-8")
    logger.info("日志已清空: %s", log_type)
    return True


# ── 系统信息 ───────────────────────────────────────────────

def get_system_info() -> dict:
    """获取系统基本信息"""
    import platform
    import sys
    return {
        "app_name": "MultiMount",
        "version": "0.1.0",
        "python_version": sys.version,
        "platform": platform.platform(),
        "hostname": platform.node(),
    }
