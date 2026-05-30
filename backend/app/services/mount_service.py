import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import *  # noqa: F401,F403 — trigger adapter registration
from app.adapters.base import BaseAdapter
from app.adapters.registry import AdapterRegistry
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.security import decrypt_field, encrypt_field
from app.models.mount import Mount

# 敏感配置字段列表 — 存储时加密, 返回时脱敏
_SENSITIVE_KEYS = {"password", "access_key_secret", "private_key"}
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MANAGED_MOUNT_ROOT = PROJECT_ROOT / "mount_points"
_INVALID_DIR_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _encrypt_config(config: dict) -> dict:
    """加密配置中的敏感字段"""
    encrypted = {}
    for k, v in config.items():
        if k in _SENSITIVE_KEYS and isinstance(v, str) and v:
            encrypted[k] = encrypt_field(v)
        else:
            encrypted[k] = v
    return encrypted


def _decrypt_config(config: dict) -> dict:
    """解密配置中的敏感字段"""
    decrypted = {}
    for k, v in config.items():
        if k in _SENSITIVE_KEYS and isinstance(v, str) and v:
            try:
                decrypted[k] = decrypt_field(v)
            except Exception:
                decrypted[k] = v
        else:
            decrypted[k] = v
    return decrypted


def _mask_config(config: dict) -> dict:
    """返回时脱敏: 密码等字段显示为 ******"""
    masked = {}
    for k, v in config.items():
        if k in _SENSITIVE_KEYS and isinstance(v, str) and v:
            masked[k] = "******"
        else:
            masked[k] = v
    return masked


def _get_adapter(mount: Mount) -> BaseAdapter:
    """根据挂载记录创建适配器实例"""
    config = _decrypt_config(mount.config)
    return AdapterRegistry.create(mount.type, config)


def _safe_managed_dir_base(name: str) -> str:
    cleaned = _INVALID_DIR_CHARS.sub("_", name).strip().strip(".")
    return cleaned or "未命名挂载"


def _create_managed_mount_dir(name: str) -> Path:
    MANAGED_MOUNT_ROOT.mkdir(parents=True, exist_ok=True)
    base = _safe_managed_dir_base(name)
    for index in range(0, 1000):
        dirname = base if index == 0 else f"{base}（{index}）"
        path = MANAGED_MOUNT_ROOT / dirname
        try:
            path.mkdir()
            return path
        except FileExistsError:
            continue
    raise BadRequestException("无法创建托管挂载目录，请更换挂载名称")


async def _refresh_mount_capacity(mount: Mount) -> None:
    adapter = _get_adapter(mount)
    try:
        await adapter.connect()
        stats = await adapter.get_tree_stats("/")
    except Exception:
        stats = None
    finally:
        try:
            await adapter.disconnect()
        except Exception:
            pass

    if stats:
        mount.capacity_used = stats.get("file_count")
        mount.capacity_total = stats.get("total_size")
    else:
        mount.capacity_used = None
        mount.capacity_total = None


async def refresh_mount_stats(mount: Mount) -> None:
    """刷新挂载的文件统计信息。"""
    await _refresh_mount_capacity(mount)


async def list_mounts(db: AsyncSession) -> list[Mount]:
    result = await db.execute(select(Mount).order_by(Mount.id))
    return list(result.scalars().all())


async def get_mount(db: AsyncSession, mount_id: int) -> Mount:
    result = await db.execute(select(Mount).where(Mount.id == mount_id))
    mount = result.scalar_one_or_none()
    if mount is None:
        raise NotFoundException("挂载点不存在")
    return mount


async def create_mount(db: AsyncSession, name: str, mount_type: str,
                       config: dict, advanced_config: dict | None = None,
                       user_id: int | None = None) -> Mount:
    """创建挂载点, user_id 记录创建者"""
    if mount_type not in AdapterRegistry.supported_types():
        raise BadRequestException(f"不支持的挂载类型: {mount_type}")

    if mount_type == "managed":
        mount_dir = _create_managed_mount_dir(name)
        config = {
            "path": str(mount_dir),
            "directory_name": mount_dir.name,
            "managed": True,
        }

    mount = Mount(
        name=name,
        type=mount_type,
        config=_encrypt_config(config),
        advanced_config=advanced_config,
        user_id=user_id,
    )
    db.add(mount)
    await db.flush()
    await db.refresh(mount)
    if mount_type == "managed":
        await _refresh_mount_capacity(mount)
        await db.flush()
    return mount


async def update_mount(db: AsyncSession, mount_id: int, **kwargs) -> Mount:
    mount = await get_mount(db, mount_id)
    for key, value in kwargs.items():
        if value is not None and hasattr(mount, key):
            if key == "config":
                mount.config = _encrypt_config(value)
            else:
                setattr(mount, key, value)
    await db.flush()
    await db.refresh(mount)
    return mount


async def delete_mount(db: AsyncSession, mount_id: int, user_id: int | None = None,
                      is_admin: bool = False) -> None:
    """
    删除挂载点。权限规则:
    - 管理员可删除任意挂载
    - 普通用户仅可删除自己创建的挂载 (user_id 匹配)
    - 系统预置挂载 (user_id=None) 仅管理员可删
    """
    mount = await get_mount(db, mount_id)
    if not is_admin:
        if mount.user_id is None or mount.user_id != user_id:
            raise BadRequestException("只能删除自己创建的挂载")

    # 如果管理员删除他人挂载, 通知挂载创建者
    if is_admin and mount.user_id is not None and mount.user_id != user_id:
        from app.services.notification_service import create_notification
        await create_notification(
            db, mount.user_id,
            "mount_deleted",
            "挂载被管理员删除",
            f"您的挂载 \"{mount.name}\" 已被管理员删除。",
            related_id=mount.id,
        )

    await db.delete(mount)
    await db.flush()


async def test_mount_connection(db: AsyncSession, mount_id: int) -> bool:
    """测试挂载点连接"""
    mount = await get_mount(db, mount_id)
    previous_status = mount.status
    adapter = _get_adapter(mount)
    try:
        ok = await adapter.test_connection()
        if ok:
            mount.status = "online"
            mount.last_connected_at = datetime.now(timezone.utc)
            await _refresh_mount_capacity(mount)
        else:
            mount.status = "offline"
            mount.capacity_used = None
            mount.capacity_total = None
        await db.flush()

        # 连接失败且之前是在线状态, 通知挂载创建者
        if not ok and previous_status == "online" and mount.user_id:
            from app.services.notification_service import create_notification
            await create_notification(
                db, mount.user_id,
                "mount_status",
                "挂载连接失败",
                f"挂载 \"{mount.name}\" 连接测试失败, 状态已变为离线。",
                related_id=mount.id,
            )

        return ok
    except Exception:
        mount.status = "offline"
        await db.flush()

        # 异常也通知
        if previous_status == "online" and mount.user_id:
            from app.services.notification_service import create_notification
            await create_notification(
                db, mount.user_id,
                "mount_status",
                "挂载连接异常",
                f"挂载 \"{mount.name}\" 连接时发生异常, 状态已变为离线。",
                related_id=mount.id,
            )

        return False


async def get_adapter_for_mount(db: AsyncSession, mount_id: int) -> tuple[Mount, BaseAdapter]:
    """获取挂载点及其适配器 (用于文件操作)"""
    mount = await get_mount(db, mount_id)
    adapter = _get_adapter(mount)
    return mount, adapter


def get_mount_config_masked(mount: Mount) -> dict:
    """返回脱敏后的配置 (用于 API 响应)"""
    return _mask_config(mount.config)
