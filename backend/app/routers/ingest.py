from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import AuthDep, DbSession
from app.schemas.property import PropertyDetail
from app.services.url_ingest_service import ingest_from_url

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestUrlRequest(BaseModel):
    url: str


@router.post("/url", response_model=PropertyDetail)
async def ingest_property_url(
    request: IngestUrlRequest, db: DbSession, _: AuthDep
) -> PropertyDetail:
    prop = await ingest_from_url(request.url, db)
    return PropertyDetail.model_validate(prop)
