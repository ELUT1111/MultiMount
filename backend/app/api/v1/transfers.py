"""
传输任务路由 — 任务 CRUD、暂停/恢复/取消、WebSocket 进度推送。
"""
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.transfer import TransferCreateRequest, TransferTaskOut
from app.services import transfer_service
from app.core.security import decode_token

router = APIRouter()


@router.get("", response_model=list[TransferTaskOut])
async def list_tasks(
    status: str | None = Query(None, description="按状态过滤: pending/running/paused/completed/failed"),
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询当前用户的传输任务列表"""
    return await transfer_service.list_tasks(db, _user.id, status)


@router.get("/{task_id}", response_model=TransferTaskOut)
async def get_task(
    task_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个传输任务详情"""
    return await transfer_service.get_task(db, task_id)


@router.post("", response_model=TransferTaskOut, status_code=201)
async def create_task(
    body: TransferCreateRequest,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建传输任务 — 自动提交到后台异步执行"""
    return await transfer_service.create_task(
        db, _user.id, body.type, body.mount_id,
        body.source_path, body.target_path,
        body.file_name, body.file_size,
    )


@router.post("/{task_id}/pause", response_model=TransferTaskOut)
async def pause_task(
    task_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """暂停传输任务"""
    return await transfer_service.pause_task(db, task_id)


@router.post("/{task_id}/resume", response_model=TransferTaskOut)
async def resume_task(
    task_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """恢复传输任务 (断点续传)"""
    return await transfer_service.resume_task(db, task_id)


@router.delete("/{task_id}")
async def cancel_task(
    task_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消/删除传输任务"""
    await transfer_service.cancel_task(db, task_id)
    return {"message": "已取消"}


@router.post("/{task_id}/retry", response_model=TransferTaskOut)
async def retry_task(
    task_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重试失败的传输任务"""
    task = await transfer_service.get_task(db, task_id)
    if task.status != "failed":
        from app.core.exceptions import BadRequestException
        raise BadRequestException("只能重试失败的任务")
    task.status = "pending"
    task.transferred = 0
    task.error_message = None
    await db.flush()
    return await transfer_service.resume_task(db, task_id)


# ── WebSocket: 实时传输进度 ────────────────────────────────

@router.websocket("/ws")
async def transfer_ws(websocket: WebSocket):
    """
    WebSocket 端点 — 客户端连接后自动推送传输进度。
    连接时需在 query 参数中传递 token: ws://host/api/v1/transfers/ws?token=xxx
    """
    await websocket.accept()

    # 从 query 参数中提取 token 并验证
    token = websocket.query_params.get("token", "")
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=4001, reason="无效的令牌")
        return

    user_id = int(payload["sub"])
    transfer_service.register_ws(user_id, websocket)

    try:
        # 保持连接, 等待客户端断开
        while True:
            # 接收客户端消息 (心跳/命令)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        transfer_service.unregister_ws(user_id, websocket)
