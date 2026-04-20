import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import AuthDep, DbSession
from app.models.property import Property
from app.schemas.property import CompareRequest, CompareResponse, PropertyDetail
from app.schemas.search import SearchRequest, SearchResponse
from app.services.comparison_service import generate_comparison
from app.services.search_service import semantic_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/semantic", response_model=SearchResponse)
async def search_properties(request: SearchRequest, db: DbSession, _: AuthDep) -> SearchResponse:
    result = await semantic_search(request, db)
    return SearchResponse(**result)


@router.get("/properties/{property_id}", response_model=PropertyDetail)
async def get_property(property_id: uuid.UUID, db: DbSession, _: AuthDep) -> PropertyDetail:
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return PropertyDetail.model_validate(prop)


@router.post("/properties/compare", response_model=CompareResponse)
async def compare_properties(request: CompareRequest, db: DbSession, _: AuthDep) -> CompareResponse:
    result = await db.execute(
        select(Property).where(Property.id.in_(request.property_ids))
    )
    props = result.scalars().all()
    if len(props) != len(request.property_ids):
        raise HTTPException(status_code=404, detail="One or more properties not found")
    data = generate_comparison(list(props))
    from app.schemas.property import PropertySummary
    return CompareResponse(
        summary=data["summary"],
        properties=[PropertySummary.model_validate(p) for p in props],
        comparison_table=data["comparison_table"],
    )
