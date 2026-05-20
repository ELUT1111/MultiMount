"""
文件操作路由 — 提供跨挂载点的统一文件 CRUD + 流式上传/下载接口。
所有路由通过 mount_id 定位挂载点, path 参数指定虚拟路径。
权限校验: 读操作需 read 权限, 写操作需 readwrite 权限。
"""
from pathlib import PurePosixPath
import os
import tempfile
import zipfile
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, UploadFile, File as FastAPIFile
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.core.policy import enforce_file_policy
from app.core.mount_permissions import require_file_action
from app.schemas.file import (
    BatchFileRequest,
    BatchFileResponse,
    BatchFileResult,
    BatchDownloadRequest,
    DirectoryStatsOut,
    FileInfoOut,
    MoveCopyRequest,
    MultipartUploadInit,
    MultipartUploadInitOut,
)
from app.services import file_service, operation_log_service, upload_session_service
from app.utils.path_utils import normalize_path, safe_upload_filename

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


@router.post("/batch-download")
async def batch_download_zip(
    request: Request,
    body: BatchDownloadRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """将多挂载、多文件/目录打包为 ZIP 下载。"""
    tmp = tempfile.NamedTemporaryFile(prefix="mounthub_", suffix=".zip", delete=False)
    tmp_path = tmp.name
    tmp.close()

    used_names: set[str] = set()

    def unique_name(name: str) -> str:
        safe = name.strip("/").replace("\\", "/") or "files"
        if safe not in used_names:
            used_names.add(safe)
            return safe
        stem, dot, suffix = safe.rpartition(".")
        for i in range(1, 10000):
            candidate = f"{stem} ({i}).{suffix}" if dot else f"{safe} ({i})"
            if candidate not in used_names:
                used_names.add(candidate)
                return candidate
        return safe

    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in body.items:
                await enforce_file_policy(db, current_user, item.mount_id, "download")
                info = await file_service.get_info(db, item.mount_id, item.path)
                root_name = unique_name(info.name or PurePosixPath(item.path).name or f"mount-{item.mount_id}")
                async for relative_path, file_info in file_service.iter_files_recursive(
                    db, item.mount_id, item.path, base_name=root_name
                ):
                    if file_info.is_dir:
                        continue
                    with zf.open(relative_path, "w") as dest:
                        async for chunk in file_service.download_file(db, item.mount_id, file_info.path):
                            dest.write(chunk)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="file_batch_download_zip",
        user=current_user,
        resource_type="file",
        ip_address=ip,
        user_agent=user_agent,
        detail={"item_count": len(body.items), "size": os.path.getsize(tmp_path)},
    )

    return FileResponse(
        tmp_path,
        media_type="application/zip",
        filename="mounthub-download.zip",
        background=BackgroundTask(lambda: os.path.exists(tmp_path) and os.unlink(tmp_path)),
    )


@router.get("/{mount_id}/stats", response_model=DirectoryStatsOut)
async def directory_stats(
    mount_id: int,
    path: str = Query(..., description="文件或目录路径"),
    _user=Depends(require_file_action("info")),
    db: AsyncSession = Depends(get_db),
):
    """递归统计目录大小、文件数量和目录数量。"""
    return await file_service.directory_stats(db, mount_id, path)


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
    await file_service.delete_file(db, mount_id, path, user=current_user)
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
    return {"message": "已移入回收站"}


def _batch_target_path(source_path: str, target_dir: str | None, explicit_target: str | None) -> str | None:
    if explicit_target:
        return normalize_path(explicit_target)
    if not target_dir:
        return None
    name = PurePosixPath(normalize_path(source_path)).name
    return normalize_path(target_dir.rstrip("/") + "/" + name)


@router.post("/{mount_id}/batch", response_model=BatchFileResponse)
async def batch_file_operation(
    request: Request,
    mount_id: int,
    body: BatchFileRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch delete/move/copy within one mount and return per-item results."""
    await enforce_file_policy(db, current_user, mount_id, body.action)
    results: list[BatchFileResult] = []

    for item in body.items:
        source_path = normalize_path(item.path)
        target_path = _batch_target_path(source_path, body.target_dir, item.target_path)
        try:
            if body.action == "delete":
                await file_service.delete_file(db, mount_id, source_path, user=current_user)
            elif body.action == "move":
                if not target_path:
                    raise ValueError("target_dir or target_path is required")
                await file_service.move_file(db, mount_id, source_path, target_path, body.conflict_policy)
            elif body.action == "copy":
                if not target_path:
                    raise ValueError("target_dir or target_path is required")
                await file_service.copy_file(db, mount_id, source_path, target_path, body.conflict_policy)
            results.append(BatchFileResult(path=source_path, target_path=target_path, success=True))
        except Exception as exc:
            results.append(
                BatchFileResult(
                    path=source_path,
                    target_path=target_path,
                    success=False,
                    message=getattr(exc, "detail", str(exc)),
                )
            )

    success_count = sum(1 for item in results if item.success)
    failed_count = len(results) - success_count
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action=f"file_batch_{body.action}",
        user=current_user,
        mount_id=mount_id,
        status="success" if failed_count == 0 else "partial_failed",
        ip_address=ip,
        user_agent=user_agent,
        detail={
            "success_count": success_count,
            "failed_count": failed_count,
            "items": [item.model_dump() for item in results],
        },
    )
    return BatchFileResponse(results=results, success_count=success_count, failed_count=failed_count)


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
