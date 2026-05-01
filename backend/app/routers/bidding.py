import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import AuthDep, DbSession
from app.models.bid import BidEntry, BidSession
from app.models.price_model_result import PriceModelResult
from app.models.property import Property
from app.schemas.bidding import (
    BidEntryCreate,
    BidEntryOut,
    BidLetterRequest,
    BidLetterResponse,
    BidSessionCreate,
    BidSessionOut,
)
from app.schemas.pricing import PriceModelResultOut
from app.services.bidding_service import generate_bid_letter, generate_strategy

router = APIRouter(prefix="/bidding", tags=["bidding"])


@router.post("/sessions", response_model=BidSessionOut)
async def create_session(
    request: BidSessionCreate, db: DbSession, _: AuthDep
) -> BidSessionOut:
    result = await db.execute(select(Property).where(Property.id == request.property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    try:
        strategy: str | None = generate_strategy(prop, request.user_max_budget)
    except Exception:
        strategy = None
    session = BidSession(
        property_id=request.property_id,
        user_max_budget=request.user_max_budget,
        strategy_advice=strategy,
    )
    db.add(session)
    await db.commit()
    # Re-fetch with relationships loaded to avoid lazy-load outside async context
    fresh = await db.execute(
        select(BidSession)
        .where(BidSession.id == session.id)
        .options(selectinload(BidSession.entries))
    )
    return BidSessionOut.model_validate(fresh.scalar_one())


@router.get("/sessions/{session_id}", response_model=BidSessionOut)
async def get_session(session_id: uuid.UUID, db: DbSession, _: AuthDep) -> BidSessionOut:
    result = await db.execute(
        select(BidSession)
        .where(BidSession.id == session_id)
        .options(selectinload(BidSession.entries))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return BidSessionOut.model_validate(session)


@router.post("/sessions/{session_id}/bids", response_model=BidEntryOut)
async def add_bid(
    session_id: uuid.UUID, request: BidEntryCreate, db: DbSession, _: AuthDep
) -> BidEntryOut:
    result = await db.execute(select(BidSession).where(BidSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    entry = BidEntry(
        session_id=session_id,
        bid_amount=request.bid_amount,
        submitted_by=request.submitted_by,
        notes=request.notes,
        is_winning=request.submitted_by == "user",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return BidEntryOut.model_validate(entry)


@router.get("/sessions/{session_id}/price-model", response_model=PriceModelResultOut)
async def get_price_model(session_id: uuid.UUID, db: DbSession, _: AuthDep) -> PriceModelResultOut:
    result = await db.execute(select(BidSession).where(BidSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    model_result = await db.execute(
        select(PriceModelResult)
        .where(PriceModelResult.property_id == session.property_id)
        .order_by(PriceModelResult.run_at.desc())
        .limit(1)
    )
    latest = model_result.scalars().first()
    if not latest:
        raise HTTPException(status_code=404, detail="No price model run yet. POST to /pricing/analyse first.")
    return PriceModelResultOut.model_validate(latest)


@router.post("/sessions/{session_id}/bid-letter", response_model=BidLetterResponse)
async def create_bid_letter(
    session_id: uuid.UUID, request: BidLetterRequest, db: DbSession, _: AuthDep
) -> BidLetterResponse:
    result = await db.execute(
        select(BidSession).where(BidSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    prop_result = await db.execute(select(Property).where(Property.id == session.property_id))
    prop = prop_result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    try:
        letter = generate_bid_letter(prop, request.user_bid, request.competing_bid, request.additional_context or "")
    except Exception:
        letter = "[Bid letter generation unavailable — Bedrock not configured. Set real AWS credentials to enable this.]"
    return BidLetterResponse(letter_text=letter)
