"""
文件操作路由 — 提供跨挂载点的统一文件 CRUD + 流式上传/下载接口。
所有路由通过 mount_id 定位挂载点, path 参数指定虚拟路径。
权限校验: 读操作需 read 权限, 写操作需 readwrite 权限。
"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, UploadFile, File as FastAPIFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.mount_permissions import require_file_action
from app.schemas.file import FileInfoOut, MoveCopyRequest, MultipartUploadInit, MultipartUploadInitOut
from app.services import file_service, operation_log_service, upload_session_service
from app.utils.path_utils import safe_upload_filename

router = APIRouter()


def _download_headers(filename: str, size: int | None) -> dict[str, str]:
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
    }
    if size is not None:
        headers["Content-Length"] = str(size)
    return headers


@router.get("/{mount_id}/list", response_model=list[FileInfoOut])
async def list_files(
    mount_id: int,
    path: str = Query("/", description="目录路径"),
    _user=Depends(require_file_action("list")),
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
    _user=Depends(require_file_action("info")),
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
    request: Request,
    mount_id: int,
    path: str = Query(..., description="文件路径"),
    current_user=Depends(require_file_action("download")),
    db: AsyncSession = Depends(get_db),
):
    """流式下载文件 — 使用 StreamingResponse 逐块返回, 支持大文件"""
    info = await file_service.get_info(db, mount_id, path)
    mime = info.mime_type or "application/octet-stream"
    filename = info.name

    async def stream_with_db():
        async for chunk in file_service.download_file(db, mount_id, path):
            yield chunk

    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="file_download",
        user=current_user,
        mount_id=mount_id,
        path=path,
        ip_address=ip,
        user_agent=user_agent,
        detail={"size": info.size, "name": filename},
    )

    return StreamingResponse(
        stream_with_db(),
        media_type=mime,
        headers=_download_headers(filename, info.size),
    )


@router.post("/{mount_id}/upload", response_model=FileInfoOut)
async def upload_file(
    request: Request,
    mount_id: int,
    path: str = Query("/", description="目标目录路径"),
    conflict_policy: str = Query("error", pattern="^(error|overwrite|skip|rename)$"),
    file: UploadFile = FastAPIFile(...),
    current_user=Depends(require_file_action("upload")),
    db: AsyncSession = Depends(get_db),
):
    """上传文件 — 接收 multipart/form-data, 流式写入目标挂载点"""
    filename = safe_upload_filename(file.filename)
    target_path = path.rstrip("/") + "/" + filename

    async def file_chunk_iter():
        while chunk := await file.read(64 * 1024):
            yield chunk

    info = await file_service.upload_file(
        db, mount_id, target_path, file_chunk_iter(), file.size, conflict_policy=conflict_policy
    )
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="file_upload",
        user=current_user,
        mount_id=mount_id,
        path=target_path,
        ip_address=ip,
        user_agent=user_agent,
        detail={"size": info.size, "name": info.name},
    )
    return FileInfoOut(
        name=info.name, path=info.path, is_dir=info.is_dir,
        size=info.size, modified_at=info.modified_at, created_at=info.created_at,
        mime_type=info.mime_type, permissions=info.permissions,
    )


@router.post("/{mount_id}/mkdir", response_model=FileInfoOut)
async def make_directory(
    request: Request,
    mount_id: int,
    path: str = Query(..., description="新目录路径"),
    current_user=Depends(require_file_action("mkdir")),
    db: AsyncSession = Depends(get_db),
):
    """创建新目录"""
    info = await file_service.make_directory(db, mount_id, path)
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="file_mkdir",
        user=current_user,
        mount_id=mount_id,
        path=path,
        ip_address=ip,
        user_agent=user_agent,
    )
    return FileInfoOut(
        name=info.name, path=info.path, is_dir=info.is_dir,
        size=info.size, modified_at=info.modified_at, created_at=info.created_at,
        mime_type=info.mime_type, permissions=info.permissions,
    )


@router.post("/{mount_id}/move", response_model=FileInfoOut)
async def move_file(
    request: Request,
    mount_id: int,
    body: MoveCopyRequest,
    current_user=Depends(require_file_action("move")),
    db: AsyncSession = Depends(get_db),
):
    """移动/重命名文件或目录"""
    info = await file_service.move_file(db, mount_id, body.src, body.dst, body.conflict_policy)
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="file_move",
        user=current_user,
        mount_id=mount_id,
        path=body.src,
        target_path=body.dst,
        ip_address=ip,
        user_agent=user_agent,
    )
    return FileInfoOut(
        name=info.name, path=info.path, is_dir=info.is_dir,
        size=info.size, modified_at=info.modified_at, created_at=info.created_at,
        mime_type=info.mime_type, permissions=info.permissions,
    )


@router.post("/{mount_id}/copy", response_model=FileInfoOut)
async def copy_file(
    request: Request,
    mount_id: int,
    body: MoveCopyRequest,
    current_user=Depends(require_file_action("copy")),
    db: AsyncSession = Depends(get_db),
):
    """复制文件或目录"""
    info = await file_service.copy_file(db, mount_id, body.src, body.dst, body.conflict_policy)
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="file_copy",
        user=current_user,
        mount_id=mount_id,
        path=body.src,
        target_path=body.dst,
        ip_address=ip,
        user_agent=user_agent,
    )
    return FileInfoOut(
        name=info.name, path=info.path, is_dir=info.is_dir,
        size=info.size, modified_at=info.modified_at, created_at=info.created_at,
        mime_type=info.mime_type, permissions=info.permissions,
    )


@router.delete("/{mount_id}/delete")
async def delete_file(
    request: Request,
    mount_id: int,
    path: str = Query(..., description="文件路径"),
    current_user=Depends(require_file_action("delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除文件或目录"""
    await file_service.delete_file(db, mount_id, path)
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="file_delete",
        user=current_user,
        mount_id=mount_id,
        path=path,
        ip_address=ip,
        user_agent=user_agent,
    )
    return {"message": "已删除"}


@router.post("/{mount_id}/multipart/init", response_model=MultipartUploadInitOut)
async def init_multipart_upload(
    mount_id: int,
    body: MultipartUploadInit,
    current_user=Depends(require_file_action("upload")),
):
    """初始化浏览器分片上传会话。"""
    return await upload_session_service.init_session(
        body.filename,
        body.path,
        body.size,
        body.chunk_size,
        body.conflict_policy,
        mount_id=mount_id,
        user_id=current_user.id,
    )


@router.post("/{mount_id}/multipart/{upload_id}/chunk/{index}")
async def upload_multipart_chunk(
    mount_id: int,
    upload_id: str,
    index: int,
    chunk: UploadFile = FastAPIFile(...),
    current_user=Depends(require_file_action("upload")),
):
    """上传单个分片。"""
    async def chunk_iter():
        while data := await chunk.read(1024 * 1024):
            yield data

    return await upload_session_service.save_chunk(upload_id, index, chunk_iter(), mount_id, current_user.id)


@router.post("/{mount_id}/multipart/{upload_id}/complete", response_model=FileInfoOut)
async def complete_multipart_upload(
    request: Request,
    mount_id: int,
    upload_id: str,
    current_user=Depends(require_file_action("upload")),
    db: AsyncSession = Depends(get_db),
):
    """完成分片上传并写入目标挂载点。"""
    info = await upload_session_service.complete_session(db, mount_id, upload_id, current_user.id)
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="file_multipart_upload",
        user=current_user,
        mount_id=mount_id,
        path=info.path,
        ip_address=ip,
        user_agent=user_agent,
        detail={"size": info.size, "name": info.name, "upload_id": upload_id},
    )
    return FileInfoOut(
        name=info.name, path=info.path, is_dir=info.is_dir,
        size=info.size, modified_at=info.modified_at, created_at=info.created_at,
        mime_type=info.mime_type, permissions=info.permissions,
    )


@router.delete("/{mount_id}/multipart/{upload_id}")
async def abort_multipart_upload(
    mount_id: int,
    upload_id: str,
    current_user=Depends(require_file_action("upload")),
):
    """取消分片上传会话并清理临时文件。"""
    await upload_session_service.abort_session(upload_id, mount_id, current_user.id)
    return {"message": "已取消上传"}
