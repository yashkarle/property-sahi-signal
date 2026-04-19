from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.sql import func

from app.dependencies import AuthDep, DbSession
from app.models.professional import Professional

router = APIRouter(prefix="/professionals", tags=["professionals"])


def _distance_expr(lat: float, lon: float):
    """Haversine distance approximation in meters (Postgres)."""
    return func.sqrt(
        func.pow(69.1 * (Professional.latitude - lat), 2)
        + func.pow(69.1 * (lon - Professional.longitude) * func.cos(func.radians(lat)), 2)
    ) * 1609.34


@router.get("/solicitors")
async def list_solicitors(
    db: DbSession,
    _: AuthDep,
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    max_distance_km: float = Query(default=20.0),
) -> list[dict]:
    stmt = select(Professional).where(Professional.professional_type == "solicitor")
    if lat and lon:
        stmt = stmt.where(
            _distance_expr(lat, lon) <= max_distance_km * 1000
        ).order_by(_distance_expr(lat, lon))
    result = await db.execute(stmt.limit(50))
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "firm_name": p.firm_name,
            "address": p.address,
            "phone": p.phone,
            "email": p.email,
            "website": p.website,
            "specialties": p.specialties,
        }
        for p in result.scalars().all()
    ]


@router.get("/surveyors")
async def list_surveyors(
    db: DbSession,
    _: AuthDep,
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    max_distance_km: float = Query(default=20.0),
) -> list[dict]:
    stmt = select(Professional).where(Professional.professional_type == "surveyor")
    if lat and lon:
        stmt = stmt.where(
            _distance_expr(lat, lon) <= max_distance_km * 1000
        ).order_by(_distance_expr(lat, lon))
    result = await db.execute(stmt.limit(50))
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "firm_name": p.firm_name,
            "address": p.address,
            "phone": p.phone,
            "email": p.email,
            "website": p.website,
        }
        for p in result.scalars().all()
    ]
