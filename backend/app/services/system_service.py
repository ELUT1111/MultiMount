import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.ssl_manager import load_config, save_config, save_cert_file, validate_cert

logger = logging.getLogger("multimount.system")

LOGS_DIR = Path("logs")


def get_https_status() -> dict:
    config = load_config()
    days_remaining = None
    expiry_warning = False
    if config.cert_expiry:
        try:
            if config.cert_expiry.endswith(" UTC"):
                expiry = datetime.strptime(config.cert_expiry, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                days_remaining = max((expiry - datetime.now(timezone.utc)).days, 0)
                expiry_warning = days_remaining <= 30
        except ValueError:
            days_remaining = None

    return {
        "cert_valid": config.cert_valid,
        "cert_expiry": config.cert_expiry,
        "cert_days_remaining": days_remaining,
        "cert_expiry_warning": expiry_warning,
        "force_https": config.force_https,
        "auto_redirect": config.auto_redirect,
        "cert_path": config.cert_path,
        "key_path": config.key_path,
        "reverse_proxy": {
            "nginx": [
                "proxy_set_header Host $host;",
                "proxy_set_header X-Real-IP $remote_addr;",
                "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
                "proxy_set_header X-Forwarded-Proto $scheme;",
                "client_max_body_size 0;",
            ],
            "caddy": ["reverse_proxy 127.0.0.1:8000"],
            "notes": [
                "Set X-Forwarded-Proto to https when TLS is terminated by a reverse proxy.",
                "Enable force_https only after direct TLS or proxy TLS is working.",
            ],
        },
    }


def upload_certificate(cert_content: bytes, cert_filename: str) -> dict:
    saved_path = save_cert_file(cert_filename, cert_content)
    result = validate_cert(saved_path)

    config = load_config()
    config.cert_path = saved_path
    config.cert_valid = result["valid"]
    config.cert_expiry = result["expiry"]
    save_config(config)

    logger.info("Certificate uploaded: %s valid=%s", saved_path, result["valid"])
    return {"path": saved_path, "valid": result["valid"], "expiry": result["expiry"], "error": result.get("error")}


def upload_key(key_content: bytes, key_filename: str) -> dict:
    saved_path = save_cert_file(key_filename, key_content)

    config = load_config()
    config.key_path = saved_path
    save_config(config)

    logger.info("Private key uploaded: %s", saved_path)
    return {"path": saved_path}


def update_https_config(force_https: bool | None = None, auto_redirect: bool | None = None) -> dict:
    config = load_config()
    if force_https is not None:
        config.force_https = force_https
    if auto_redirect is not None:
        config.auto_redirect = auto_redirect
    save_config(config)
    logger.info("HTTPS config updated: force_https=%s auto_redirect=%s", config.force_https, config.auto_redirect)
    return get_https_status()


def list_logs(log_type: str = "system", start_date: str = "", end_date: str = "") -> list[dict]:
    log_file = LOGS_DIR / f"{log_type}.log"
    if not log_file.exists() and log_type == "system":
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
            if start_date and entry["timestamp"] < start_date:
                continue
            if end_date and entry["timestamp"] > end_date + " 23:59:59":
                continue
            entries.append(entry)
    except Exception as exc:
        logger.error("Failed to read logs: %s", exc)

    return entries[-500:][::-1]


def _parse_log_line(line: str) -> dict:
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
    logger.info("Log exported: %s", export_path)
    return str(export_path)


def clear_logs(log_type: str = "system") -> bool:
    log_file = LOGS_DIR / f"{log_type}.log"
    if not log_file.exists() and log_type == "system":
        log_file = LOGS_DIR / "app.log"
    if not log_file.exists():
        return False

    log_file.write_text("", encoding="utf-8")
    logger.info("Log cleared: %s", log_type)
    return True


def get_system_info() -> dict:
    import platform
    import sys

    return {
        "app_name": "MultiMount",
        "version": "0.1.0",
        "python_version": sys.version,
        "platform": platform.platform(),
        "hostname": platform.node(),
    }
