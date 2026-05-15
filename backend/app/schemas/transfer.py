"""传输任务相关的 Pydantic 数据模型"""
from datetime import datetime
from pydantic import BaseModel


class TransferTaskOut(BaseModel):
    """传输任务响应"""
    id: int
    user_id: int | None
    type: str
    status: str
    file_name: str
    file_size: int | None
    source_path: str
    target_path: str
    mount_id: int | None
    transferred: int
    chunk_size: int
    speed: float | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransferCreateRequest(BaseModel):
    """创建传输任务请求"""
    type: str  # upload / download
    mount_id: int
    source_path: str
    target_path: str
    file_name: str
    file_size: int | None = None
