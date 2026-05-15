"""文件操作相关的 Pydantic 数据模型"""
from datetime import datetime
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
