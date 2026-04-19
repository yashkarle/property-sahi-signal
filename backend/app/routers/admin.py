from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.dependencies import AuthDep, DbSession
from app.models.admin import AdminLog

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/logs")
async def get_logs(
    db: DbSession,
    _: AuthDep,
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    event_type: str | None = Query(None),
    limit: int = Query(default=100, le=1000),
) -> list[dict]:
    stmt = select(AdminLog).order_by(AdminLog.created_at.desc()).limit(limit)
    if from_date:
        stmt = stmt.where(AdminLog.created_at >= from_date)
    if to_date:
        stmt = stmt.where(AdminLog.created_at <= to_date)
    if event_type:
        stmt = stmt.where(AdminLog.event_type == event_type)
    result = await db.execute(stmt)
    return [
        {
            "id": str(log.id),
            "event_type": log.event_type,
            "endpoint": log.endpoint,
            "duration_ms": log.duration_ms,
            "bedrock_tokens_in": log.bedrock_tokens_in,
            "bedrock_tokens_out": log.bedrock_tokens_out,
            "created_at": log.created_at.isoformat(),
        }
        for log in result.scalars().all()
    ]


@router.get("/usage-summary")
async def usage_summary(db: DbSession, _: AuthDep) -> dict:
    result = await db.execute(
        select(
            AdminLog.event_type,
            func.count(AdminLog.id).label("count"),
            func.sum(AdminLog.bedrock_tokens_in).label("tokens_in"),
            func.sum(AdminLog.bedrock_tokens_out).label("tokens_out"),
            func.avg(AdminLog.duration_ms).label("avg_ms"),
        ).group_by(AdminLog.event_type)
    )
    rows = result.all()
    return {
        "by_event": [
            {
                "event_type": r.event_type,
                "count": r.count,
                "tokens_in": r.tokens_in or 0,
                "tokens_out": r.tokens_out or 0,
                "avg_duration_ms": round(float(r.avg_ms or 0), 1),
            }
            for r in rows
        ]
    }
