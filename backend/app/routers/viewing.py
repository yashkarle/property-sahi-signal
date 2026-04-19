import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import AuthDep, DbSession
from app.models.property import Property
from app.schemas.viewing import (
    EmailDraftRequest,
    EmailDraftResponse,
    MissingDataResponse,
    ViewingChecklistResponse,
    ViewingQuestionsResponse,
)
from app.services.viewing_service import (
    generate_checklist,
    generate_email_draft,
    generate_missing_data_flags,
    generate_questions,
)

router = APIRouter(prefix="/viewing", tags=["viewing"])


async def _get_prop(property_id: uuid.UUID, db: DbSession) -> Property:
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@router.get("/{property_id}/checklist", response_model=ViewingChecklistResponse)
async def get_checklist(property_id: uuid.UUID, db: DbSession, _: AuthDep) -> ViewingChecklistResponse:
    prop = await _get_prop(property_id, db)
    items = generate_checklist(prop)
    return ViewingChecklistResponse(property_id=str(property_id), items=items)


@router.get("/{property_id}/questions", response_model=ViewingQuestionsResponse)
async def get_questions(property_id: uuid.UUID, db: DbSession, _: AuthDep) -> ViewingQuestionsResponse:
    prop = await _get_prop(property_id, db)
    questions = generate_questions(prop)
    return ViewingQuestionsResponse(property_id=str(property_id), questions=questions)


@router.get("/{property_id}/missing-data", response_model=MissingDataResponse)
async def get_missing_data(property_id: uuid.UUID, db: DbSession, _: AuthDep) -> MissingDataResponse:
    prop = await _get_prop(property_id, db)
    flags = generate_missing_data_flags(prop)
    risk_flags = [f.description for f in flags if f.risk_level == "critical"]
    return MissingDataResponse(
        property_id=str(property_id),
        missing_fields=flags,
        risk_flags=risk_flags,
    )


@router.post("/{property_id}/email-draft", response_model=EmailDraftResponse)
async def draft_email(
    property_id: uuid.UUID,
    request: EmailDraftRequest,
    db: DbSession,
    _: AuthDep,
) -> EmailDraftResponse:
    prop = await _get_prop(property_id, db)
    draft = generate_email_draft(prop, request.agent_name, request.visit_date, request.additional_context or "")
    return EmailDraftResponse(**draft)
