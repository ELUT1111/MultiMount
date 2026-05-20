"""文件操作相关的 Pydantic 数据模型"""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class FileInfoOut(BaseModel):
    """文件/目录元数据响应"""
    name: str
    path: str
    is_dir: bool
    size: int
    modified_at: datetime | None
    created_at: datetime | None
    mime_type: str | None
    permissions: str | None

    model_config = {"from_attributes": True}


class MoveCopyRequest(BaseModel):
    """移动/复制请求体"""
    src: str = Field(..., description="源路径")
    dst: str = Field(..., description="目标路径")
    conflict_policy: str = Field("error", pattern="^(error|overwrite|skip|rename)$")


class BatchFileItem(BaseModel):
    """Single item in a batch file operation."""
    path: str = Field(..., min_length=1)
    target_path: str | None = None


class BatchFileRequest(BaseModel):
    """Batch delete/move/copy request."""
    action: Literal["delete", "move", "copy"]
    items: list[BatchFileItem] = Field(..., min_length=1, max_length=200)
    target_dir: str | None = None
    conflict_policy: str = Field("error", pattern="^(error|overwrite|skip|rename)$")


class BatchFileResult(BaseModel):
    path: str
    target_path: str | None = None
    success: bool
    message: str = ""


class BatchFileResponse(BaseModel):
    results: list[BatchFileResult]
    success_count: int
    failed_count: int


class BatchDownloadItem(BaseModel):
    mount_id: int
    path: str = Field(..., min_length=1)


class BatchDownloadRequest(BaseModel):
    items: list[BatchDownloadItem] = Field(..., min_length=1, max_length=200)


class DirectoryStatsOut(BaseModel):
    path: str
    total_size: int
    file_count: int
    dir_count: int


class TrashItemOut(BaseModel):
    id: int
    mount_id: int
    original_path: str
    trash_path: str
    name: str
    is_dir: bool
    size: int
    deleted_by: int | None
    deleted_by_name: str | None
    deleted_at: datetime | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class MultipartUploadInit(BaseModel):
    """初始化分片上传请求体"""
    filename: str = Field(..., min_length=1)
    path: str = Field("/", description="目标目录路径")
    size: int = Field(..., ge=0)
    chunk_size: int = Field(4 * 1024 * 1024, ge=256 * 1024, le=64 * 1024 * 1024)
    conflict_policy: str = Field("error", pattern="^(error|overwrite|skip|rename)$")


class MultipartUploadInitOut(BaseModel):
    upload_id: str
    chunk_size: int
