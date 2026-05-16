from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator


@dataclass
class FileInfo:
    """统一文件元数据结构 — 所有适配器返回此类型"""
    name: str                   # 文件名
    path: str                   # 完整路径
    is_dir: bool                # 是否为目录
    size: int                   # 文件大小 (字节), 目录为 0
    modified_at: datetime | None  # 最后修改时间
    created_at: datetime | None   # 创建时间
    mime_type: str | None       # MIME 类型, 目录为 None
    permissions: str | None     # 权限字符串


class BaseAdapter(ABC):
    """文件系统适配器抽象基类 — 所有协议实现此类"""

    @abstractmethod
    async def connect(self) -> bool:
        """建立连接, 返回是否成功"""

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接, 释放资源"""

    @abstractmethod
    async def test_connection(self) -> bool:
        """测试连接可用性"""

    @abstractmethod
    async def list_dir(self, path: str) -> list[FileInfo]:
        """列出目录内容"""

    @abstractmethod
    async def get_info(self, path: str) -> FileInfo:
        """获取文件/目录元数据"""

    @abstractmethod
    async def download(self, path: str) -> AsyncIterator[bytes]:
        """流式下载文件 (支持大文件)"""

    @abstractmethod
    async def upload(self, path: str, data: AsyncIterator[bytes],
                     size: int | None = None) -> None:
        """流式上传文件"""

    @abstractmethod
    async def delete(self, path: str) -> None:
        """删除文件/目录"""

    @abstractmethod
    async def mkdir(self, path: str) -> None:
        """创建目录"""

    @abstractmethod
    async def move(self, src: str, dst: str) -> None:
        """移动/重命名"""

    async def copy(self, src: str, dst: str) -> None:
        """复制文件 (默认实现: 流式下载再上传, 不缓冲整个文件)"""

        async def _stream():
            async for chunk in self.download(src):
                yield chunk

        await self.upload(dst, _stream())

    async def get_capacity(self) -> dict | None:
        """获取存储容量信息 {used, total}, 不支持则返回 None"""
        return None
