"""
文件操作路由 — 提供跨挂载点的统一文件 CRUD + 流式上传/下载接口。
所有路由通过 mount_id 定位挂载点, path 参数指定虚拟路径。
权限校验: 读操作需 read 权限, 写操作需 readwrite 权限。
"""
from fastapi import APIRouter, Depends, Query, UploadFile, File as FastAPIFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.mount_permissions import require_mount_access
from app.schemas.file import FileInfoOut, MoveCopyRequest
from app.services import file_service
from app.utils.file_utils import guess_mime

router = APIRouter()


@router.get("/{mount_id}/list", response_model=list[FileInfoOut])
async def list_files(
    mount_id: int,
    path: str = Query("/", description="目录路径"),
    _user=Depends(require_mount_access("read")),
    db: AsyncSession = Depends(get_db),
):
    """列出指定目录下的文件和子目录"""
    items = await file_service.list_dir(db, mount_id, path)
    return [
        FileInfoOut(
            name=item.name,
            path=item.path,
            is_dir=item.is_dir,
            size=item.size,
            modified_at=item.modified_at,
            created_at=item.created_at,
            mime_type=item.mime_type,
            permissions=item.permissions,
        )
        for item in items
    ]


@router.get("/{mount_id}/info", response_model=FileInfoOut)
async def get_file_info(
    mount_id: int,
    path: str = Query(..., description="文件路径"),
    _user=Depends(require_mount_access("read")),
    db: AsyncSession = Depends(get_db),
):
    """获取单个文件/目录的元数据"""
    item = await file_service.get_info(db, mount_id, path)
    return FileInfoOut(
        name=item.name, path=item.path, is_dir=item.is_dir,
        size=item.size, modified_at=item.modified_at, created_at=item.created_at,
        mime_type=item.mime_type, permissions=item.permissions,
    )


@router.get("/{mount_id}/download")
async def download_file(
    mount_id: int,
    path: str = Query(..., description="文件路径"),
    _user=Depends(require_mount_access("read")),
    db: AsyncSession = Depends(get_db),
):
    """流式下载文件 — 使用 StreamingResponse 逐块返回, 支持大文件"""
    info = await file_service.get_info(db, mount_id, path)
    mime = info.mime_type or "application/octet-stream"
    filename = info.name

    async def stream_with_db():
        async for chunk in file_service.download_file(db, mount_id, path):
            yield chunk

    return StreamingResponse(
        stream_with_db(),
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(info.size) if info.size else "",
        },
    )


@router.post("/{mount_id}/upload", response_model=FileInfoOut)
async def upload_file(
    mount_id: int,
    path: str = Query("/", description="目标目录路径"),
    file: UploadFile = FastAPIFile(...),
    _user=Depends(require_mount_access("readwrite")),
    db: AsyncSession = Depends(get_db),
):
    """上传文件 — 接收 multipart/form-data, 流式写入目标挂载点"""
    target_path = path.rstrip("/") + "/" + file.filename

    async def file_chunk_iter():
        while chunk := await file.read(64 * 1024):
            yield chunk

    info = await file_service.upload_file(
        db, mount_id, target_path, file_chunk_iter(), file.size
    )
    return FileInfoOut(
        name=info.name, path=info.path, is_dir=info.is_dir,
        size=info.size, modified_at=info.modified_at, created_at=info.created_at,
        mime_type=info.mime_type, permissions=info.permissions,
    )


@router.post("/{mount_id}/mkdir", response_model=FileInfoOut)
async def make_directory(
    mount_id: int,
    path: str = Query(..., description="新目录路径"),
    _user=Depends(require_mount_access("readwrite")),
    db: AsyncSession = Depends(get_db),
):
    """创建新目录"""
    info = await file_service.make_directory(db, mount_id, path)
    return FileInfoOut(
        name=info.name, path=info.path, is_dir=info.is_dir,
        size=info.size, modified_at=info.modified_at, created_at=info.created_at,
        mime_type=info.mime_type, permissions=info.permissions,
    )


@router.post("/{mount_id}/move", response_model=FileInfoOut)
async def move_file(
    mount_id: int,
    body: MoveCopyRequest,
    _user=Depends(require_mount_access("readwrite")),
    db: AsyncSession = Depends(get_db),
):
    """移动/重命名文件或目录"""
    info = await file_service.move_file(db, mount_id, body.src, body.dst)
    return FileInfoOut(
        name=info.name, path=info.path, is_dir=info.is_dir,
        size=info.size, modified_at=info.modified_at, created_at=info.created_at,
        mime_type=info.mime_type, permissions=info.permissions,
    )


@router.post("/{mount_id}/copy", response_model=FileInfoOut)
async def copy_file(
    mount_id: int,
    body: MoveCopyRequest,
    _user=Depends(require_mount_access("readwrite")),
    db: AsyncSession = Depends(get_db),
):
    """复制文件或目录"""
    info = await file_service.copy_file(db, mount_id, body.src, body.dst)
    return FileInfoOut(
        name=info.name, path=info.path, is_dir=info.is_dir,
        size=info.size, modified_at=info.modified_at, created_at=info.created_at,
        mime_type=info.mime_type, permissions=info.permissions,
    )


@router.delete("/{mount_id}/delete")
async def delete_file(
    mount_id: int,
    path: str = Query(..., description="文件路径"),
    _user=Depends(require_mount_access("readwrite")),
    db: AsyncSession = Depends(get_db),
):
    """删除文件或目录"""
    await file_service.delete_file(db, mount_id, path)
    return {"message": "已删除"}
