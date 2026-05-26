from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.policy import enforce_file_policy
from app.core.security import decode_token
from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.transfer import TransferCreateRequest, TransferTaskOut
from app.services import transfer_service

router = APIRouter()


async def _get_owned_task(task_id: int, user, db: AsyncSession):
    task = await transfer_service.get_task(db, task_id)
    if task.user_id != user.id:
        raise HTTPException(status_code=403, detail="No permission to operate this task")
    return task


async def _authorize_transfer(body: TransferCreateRequest, user, db: AsyncSession) -> None:
    source_mount_id = body.source_mount_id or body.mount_id
    target_mount_id = body.target_mount_id or body.mount_id

    if body.type == "copy":
        if source_mount_id is None or target_mount_id is None:
            raise HTTPException(status_code=400, detail="Copy task requires source and target mounts")
        if source_mount_id == target_mount_id:
            await enforce_file_policy(db, user, source_mount_id, "copy")
        else:
            await enforce_file_policy(db, user, source_mount_id, "download")
            await enforce_file_policy(db, user, target_mount_id, "upload")
        return

    if body.type == "move":
        if source_mount_id is None or target_mount_id is None:
            raise HTTPException(status_code=400, detail="Move task requires source and target mounts")
        if source_mount_id == target_mount_id:
            await enforce_file_policy(db, user, source_mount_id, "move")
        else:
            await enforce_file_policy(db, user, source_mount_id, "delete")
            await enforce_file_policy(db, user, target_mount_id, "upload")
        return

    raise HTTPException(status_code=400, detail="Unsupported transfer task type")


@router.get("", response_model=list[TransferTaskOut])
async def list_tasks(
    status: str | None = Query(None, description="Filter by status"),
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await transfer_service.list_tasks(db, _user.id, status)


@router.get("/{task_id}", response_model=TransferTaskOut)
async def get_task(
    task_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_owned_task(task_id, _user, db)


@router.post("", response_model=TransferTaskOut, status_code=201)
async def create_task(
    body: TransferCreateRequest,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _authorize_transfer(body, _user, db)
    return await transfer_service.create_task(
        db,
        _user.id,
        body.type,
        body.mount_id,
        body.source_path,
        body.target_path,
        body.file_name,
        body.file_size,
        source_mount_id=body.source_mount_id,
        target_mount_id=body.target_mount_id,
        conflict_policy=body.conflict_policy,
        download_limit_kbps=body.download_limit_kbps,
        upload_limit_kbps=body.upload_limit_kbps,
    )


@router.post("/{task_id}/pause", response_model=TransferTaskOut)
async def pause_task(
    task_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_task(task_id, _user, db)
    return await transfer_service.pause_task(db, task_id)


@router.post("/{task_id}/resume", response_model=TransferTaskOut)
async def resume_task(
    task_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_task(task_id, _user, db)
    return await transfer_service.resume_task(db, task_id)


@router.delete("/{task_id}")
async def cancel_task(
    task_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_task(task_id, _user, db)
    await transfer_service.cancel_task(db, task_id)
    return {"message": "cancelled"}


@router.post("/{task_id}/retry", response_model=TransferTaskOut)
async def retry_task(
    task_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_owned_task(task_id, _user, db)
    if task.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")
    task.status = "pending"
    task.transferred = 0
    task.speed = 0
    task.error_message = None
    await db.commit()
    return await transfer_service.resume_task(db, task_id)


@router.websocket("/ws")
async def transfer_ws(websocket: WebSocket):
    token = ""
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    if protocols:
        parts = [p.strip() for p in protocols.split(",")]
        if len(parts) >= 2 and parts[0] == "auth":
            token = parts[1]

    if not token:
        token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4001, reason="missing token")
        return

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=4001, reason="invalid token")
        return

    user_id = int(payload["sub"])
    await websocket.accept(subprotocol="auth")
    transfer_service.register_ws(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        transfer_service.unregister_ws(user_id, websocket)
