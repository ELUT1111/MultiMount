from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.adapters.base import BaseAdapter


class AdapterRegistry:
    """适配器工厂 — 根据挂载类型创建对应适配器实例"""

    # 注册表由各协议适配器上的 @AdapterRegistry.register(...) 填充。
    # 因此调用 create 前要确保 app.adapters 包已被导入，触发所有适配器模块加载。
    _registry: dict[str, type[BaseAdapter]] = {}

    @classmethod
    def register(cls, mount_type: str):
        """装饰器: 注册适配器类"""
        def decorator(adapter_cls: type[BaseAdapter]):
            cls._registry[mount_type] = adapter_cls
            return adapter_cls
        return decorator

    @classmethod
    def create(cls, mount_type: str, config: dict) -> BaseAdapter:
        """根据类型创建适配器实例"""
        adapter_cls = cls._registry.get(mount_type)
        if not adapter_cls:
            raise ValueError(f"不支持的挂载类型: {mount_type}")
        # config 来自挂载记录，已经在 mount_service 中完成敏感字段解密。
        return adapter_cls(**config)

    @classmethod
    def supported_types(cls) -> list[str]:
        return list(cls._registry.keys())
