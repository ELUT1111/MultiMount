from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operation_log import OperationLog


def request_context(request: Request | None) -> tuple[str | None, str | None]:
    """提取审计日志需要的客户端上下文。"""
    if request is None:
        return None, None
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip, user_agent[:512] if user_agent else None


async def log_operation(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str = "file",
    user=None,
    mount_id: int | None = None,
    path: str | None = None,
    target_path: str | None = None,
    status: str = "success",
    ip_address: str | None = None,
    user_agent: str | None = None,
    detail: dict | None = None,
) -> OperationLog:
    """写入业务操作审计日志。调用方复用当前 DB 事务。"""
    log = OperationLog(
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
        action=action,
        resource_type=resource_type,
        mount_id=mount_id,
        path=path,
        target_path=target_path,
        status=status,
        ip_address=ip_address,
        user_agent=user_agent,
        detail=detail,
    )
    db.add(log)
    await db.flush()
    return log


async def list_operation_logs(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
    action: str = "",
    username: str = "",
    mount_id: int | None = None,
    status: str = "",
) -> dict:
    query = select(OperationLog)
    count_query = select(func.count(OperationLog.id))

    filters = []
    if action:
        filters.append(OperationLog.action == action)
    if username:
        filters.append(OperationLog.username.contains(username))
    if mount_id is not None:
        filters.append(OperationLog.mount_id == mount_id)
    if status:
        filters.append(OperationLog.status == status)

    for condition in filters:
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(OperationLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": item.id,
                "user_id": item.user_id,
                "username": item.username,
                "action": item.action,
                "resource_type": item.resource_type,
                "mount_id": item.mount_id,
                "path": item.path,
                "target_path": item.target_path,
                "status": item.status,
                "ip_address": item.ip_address,
                "user_agent": item.user_agent,
                "detail": item.detail,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ],
    }
