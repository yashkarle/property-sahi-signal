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
    BidHistoryItem,
    BidLetterRequest,
    BidLetterResponse,
    BidSessionCreate,
    BidSessionOut,
    OutcomeUpdate,
    PriceModelSummary,
    PropertySummaryForHistory,
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

    pm_result = await db.execute(
        select(PriceModelResult)
        .where(PriceModelResult.property_id == request.property_id, PriceModelResult.status == "ready")
        .order_by(PriceModelResult.run_at.desc())
        .limit(1)
    )
    price_model = pm_result.scalars().first()

    # user_max_budget is the full ceiling computed by the frontend (AIP + savings − closing costs).
    # Never overwrite it with raw AIP — that loses deposit-backed headroom.
    effective_budget = request.user_max_budget
    try:
        strategy: str | None = generate_strategy(
            prop, effective_budget,
            user_aip=request.user_aip,
            user_savings=request.user_savings,
            price_model=price_model,
        )
    except Exception:
        strategy = None

    session = BidSession(
        property_id=request.property_id,
        user_max_budget=effective_budget,
        user_aip=request.user_aip,
        user_savings=request.user_savings,
        strategy_advice=strategy,
    )
    db.add(session)
    await db.commit()
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


@router.patch("/sessions/{session_id}/outcome", response_model=BidSessionOut)
async def record_outcome(
    session_id: uuid.UUID, request: OutcomeUpdate, db: DbSession, _: AuthDep
) -> BidSessionOut:
    result = await db.execute(
        select(BidSession)
        .where(BidSession.id == session_id)
        .options(selectinload(BidSession.entries))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = request.outcome
    session.actual_sale_price = request.actual_sale_price  # None clears a previously recorded price
    await db.commit()

    fresh = await db.execute(
        select(BidSession)
        .where(BidSession.id == session_id)
        .options(selectinload(BidSession.entries))
    )
    return BidSessionOut.model_validate(fresh.scalar_one())


@router.get("/history", response_model=list[BidHistoryItem])
async def get_bid_history(db: DbSession, _: AuthDep) -> list[BidHistoryItem]:
    sessions_result = await db.execute(
        select(BidSession)
        .options(selectinload(BidSession.entries), selectinload(BidSession.property))
        .order_by(BidSession.started_at.desc())
    )
    sessions = sessions_result.scalars().all()

    # Batch-load the latest price model result per property to avoid N+1 queries
    property_ids = list({s.property_id for s in sessions})
    pm_by_prop: dict[uuid.UUID, PriceModelResult] = {}
    if property_ids:
        pm_rows_result = await db.execute(
            select(PriceModelResult)
            .where(
                PriceModelResult.property_id.in_(property_ids),
                PriceModelResult.status == "ready",
            )
            .order_by(PriceModelResult.run_at.desc())
        )
        for pm_row in pm_rows_result.scalars().all():
            # Keep only the most recent per property (rows already ordered desc)
            if pm_row.property_id not in pm_by_prop:
                pm_by_prop[pm_row.property_id] = pm_row

    items: list[BidHistoryItem] = []
    for session in sessions:
        your_max = max(
            (e.bid_amount for e in session.entries if e.submitted_by == "user"),
            default=None,
        )
        competing_max = max(
            (e.bid_amount for e in session.entries if e.submitted_by == "other_buyer"),
            default=None,
        )

        pm = pm_by_prop.get(session.property_id)
        pm_summary = PriceModelSummary(
            offer_entry=pm.offer_entry,
            offer_sealed=pm.offer_sealed,
            p25=pm.p25_estimate,
            p50=pm.p50_estimate,
            sealed_bid_probability=(
                float(pm.sealed_bid_probability) if pm.sealed_bid_probability is not None else None
            ),
        ) if pm else None

        items.append(BidHistoryItem(
            session_id=session.id,
            property=PropertySummaryForHistory.model_validate(session.property),
            status=session.status,
            user_max_budget=session.user_max_budget,
            user_aip=session.user_aip,
            user_savings=session.user_savings,
            started_at=session.started_at,
            your_max_bid=your_max,
            competing_max_bid=competing_max,
            actual_sale_price=session.actual_sale_price,
            latest_price_model=pm_summary,
        ))

    return items


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
    result = await db.execute(select(BidSession).where(BidSession.id == session_id))
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
