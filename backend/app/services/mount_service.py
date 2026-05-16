from datetime import datetime, timezone

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
    await db.delete(mount)
    await db.flush()


async def test_mount_connection(db: AsyncSession, mount_id: int) -> bool:
    """测试挂载点连接"""
    mount = await get_mount(db, mount_id)
    adapter = _get_adapter(mount)
    try:
        ok = await adapter.test_connection()
        if ok:
            mount.status = "online"
            mount.last_connected_at = datetime.now(timezone.utc)
        else:
            mount.status = "offline"
        await db.flush()
        return ok
    except Exception:
        mount.status = "offline"
        await db.flush()
        return False


async def get_adapter_for_mount(db: AsyncSession, mount_id: int) -> tuple[Mount, BaseAdapter]:
    """获取挂载点及其适配器 (用于文件操作)"""
    mount = await get_mount(db, mount_id)
    adapter = _get_adapter(mount)
    return mount, adapter


def get_mount_config_masked(mount: Mount) -> dict:
    """返回脱敏后的配置 (用于 API 响应)"""
    return _mask_config(mount.config)
