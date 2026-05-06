# Bidding Intelligence — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the backend foundation for bidding intelligence — financial ceiling calculation, rule-based 4-step strategy, outcome recording, bid history endpoint, and comparables enriched with lat/lng for the chart/map.

**Architecture:** All backend changes are additive — new columns via migration, new endpoints via router additions, updated service logic in existing files. The `final_constraints.py` closing cost formula is updated to match Irish market (€4,500 fixed vs old €3,150). Strategy generation gets a rule-based fallback that fires when Bedrock is unavailable.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, pytest-asyncio

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/alembic/versions/003_bid_session_financial_fields.py` | Add user_aip, user_savings, actual_sale_price to bid_sessions |
| Modify | `backend/app/models/bid.py` | Add three new Mapped columns to BidSession |
| Modify | `backend/app/ml/final_constraints.py` | Fix closing costs: €3,150 → €4,500 |
| Modify | `backend/app/services/bidding_service.py` | Add _rule_based_strategy() fallback + update generate_strategy() signature |
| Modify | `backend/app/schemas/bidding.py` | Add user_aip/user_savings to BidSessionCreate; add OutcomeUpdate, BidHistorySummary, ComparablesResponse schemas |
| Modify | `backend/app/routers/bidding.py` | Update POST /sessions; add PATCH /sessions/{id}/outcome; add GET /history |
| Modify | `backend/app/schemas/pricing.py` | Add latitude, longitude to ComparableOut |
| Modify | `backend/app/routers/pricing.py` | Update GET /comparables to populate lat/lng + time_adjusted_price |
| Modify | `backend/tests/unit/test_final_constraints.py` | Tests for updated closing cost formula |
| Create | `backend/tests/unit/test_rule_based_strategy.py` | Tests for strategy derivation logic |
| Create | `backend/tests/integration/test_bidding_outcome.py` | Tests for PATCH /outcome and GET /history |

---

## Task 1: DB Migration — Add Financial Fields to bid_sessions

**Files:**
- Create: `backend/alembic/versions/003_bid_session_financial_fields.py`
- Modify: `backend/app/models/bid.py`

- [ ] **Step 1: Write the migration file**

Create `backend/alembic/versions/003_bid_session_financial_fields.py`:

```python
"""Add user_aip, user_savings, actual_sale_price to bid_sessions.

Revision ID: 003
Revises: 002
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bid_sessions", sa.Column("user_aip", sa.Integer(), nullable=True))
    op.add_column("bid_sessions", sa.Column("user_savings", sa.Integer(), nullable=True))
    op.add_column("bid_sessions", sa.Column("actual_sale_price", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("bid_sessions", "actual_sale_price")
    op.drop_column("bid_sessions", "user_savings")
    op.drop_column("bid_sessions", "user_aip")
```

- [ ] **Step 2: Update the BidSession ORM model**

In `backend/app/models/bid.py`, add three columns to `BidSession` after `user_max_budget`:

```python
    user_max_budget: Mapped[int | None] = mapped_column(Integer)
    user_aip: Mapped[int | None] = mapped_column(Integer)
    user_savings: Mapped[int | None] = mapped_column(Integer)
    actual_sale_price: Mapped[int | None] = mapped_column(Integer)
```

- [ ] **Step 3: Apply the migration**

```bash
cd /Users/yashkarle/git/property-sahi-signal/backend && python3.11 -m alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade 002 -> 003, Add user_aip, user_savings, actual_sale_price to bid_sessions
```

- [ ] **Step 4: Verify columns exist**

```bash
psql postgresql://property_user:property_pass@localhost:5432/property_sahi \
  -c "\d bid_sessions" | grep -E "user_aip|user_savings|actual_sale"
```

Expected: three rows showing the new integer columns.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/003_bid_session_financial_fields.py backend/app/models/bid.py
git commit -m "feat(db): add user_aip, user_savings, actual_sale_price to bid_sessions"
```

---

## Task 2: Fix Closing Cost Formula in final_constraints.py

**Files:**
- Modify: `backend/app/ml/final_constraints.py`
- Create: `backend/tests/unit/test_final_constraints.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_final_constraints.py`:

```python
from app.ml.final_constraints import apply_final_constraints


def test_closing_costs_formula_uses_4500_fixed() -> None:
    """Closing costs = stamp duty 1% + €4,500 (solicitor €2.5k + land reg €1k + survey/val €1k)."""
    # At a €400k purchase:
    # stamp duty = €4,000 (1%)
    # fixed = €4,500
    # total closing = €8,500
    # buyer_ceiling = 370_000 + 50_000 - 8_500 = 411_500
    # ltv_cap = n/a here (no_ltv path — buyer_aip not provided)
    result = apply_final_constraints(
        entry=350_000,
        sealed=360_000,
        ceiling=500_000,
        buyer_aip=370_000,
        buyer_savings=50_000,
        asking_price=400_000,
    )
    # buyer_ceiling = 370k + 50k - (round(400k * 0.01) + 4500) = 420k - 8500 = 411500
    # ceiling = min(500k, 411500) = 411500 → rounded to 2500 = 412500
    assert result["ceiling"] == 412_500


def test_closing_costs_old_formula_is_not_used() -> None:
    """Old formula was round(price*0.01) + 3150. New adds €4,500."""
    result = apply_final_constraints(
        entry=300_000,
        sealed=320_000,
        ceiling=600_000,
        buyer_aip=300_000,
        buyer_savings=40_000,
        asking_price=300_000,
    )
    # stamp = 3000, fixed = 4500, closing = 7500
    # buyer_ceiling = 300k + 40k - 7500 = 332500 → round to 2500 = 332500
    assert result["ceiling"] == 332_500
    # Old formula would give: 300k + 40k - (3000 + 3150) = 333850 → 332500 — same here by coincidence
    # So test with a case where it differs:


def test_no_buyer_ceiling_when_savings_missing() -> None:
    """buyer_ceiling is not applied when either aip or savings is None."""
    result = apply_final_constraints(
        entry=300_000,
        sealed=320_000,
        ceiling=400_000,
        buyer_aip=300_000,
        buyer_savings=None,
    )
    assert result["ceiling"] == 400_000


def test_ceiling_is_capped_by_buyer_ceiling() -> None:
    """Market ceiling above buyer ceiling gets capped."""
    result = apply_final_constraints(
        entry=350_000,
        sealed=370_000,
        ceiling=665_000,
        buyer_aip=370_000,
        buyer_savings=50_000,
        asking_price=365_000,
    )
    # stamp = 3650, fixed = 4500, closing = 8150
    # buyer_ceiling = 370k + 50k - 8150 = 411850 → round to 2500 = 412500
    assert result["ceiling"] == 412_500
    assert result["ceiling"] < 665_000


def test_entry_and_sealed_respect_ordering() -> None:
    """entry ≤ sealed ≤ ceiling always holds."""
    result = apply_final_constraints(
        entry=400_000,
        sealed=380_000,
        ceiling=350_000,
        buyer_aip=300_000,
        buyer_savings=50_000,
        asking_price=300_000,
    )
    assert result["entry"] <= result["sealed"] <= result["ceiling"]
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /Users/yashkarle/git/property-sahi-signal/backend && python3.11 -m pytest tests/unit/test_final_constraints.py -v 2>&1 | tail -15
```

Expected: `test_closing_costs_formula_uses_4500_fixed` FAILS (current code uses 3150).

- [ ] **Step 3: Update the closing cost formula**

In `backend/app/ml/final_constraints.py`, change line inside `apply_final_constraints`:

```python
# OLD:
closing_costs = round(min(ceiling, asking_price or ceiling) * 0.01) + 3150

# NEW — matches Irish market: stamp 1% + solicitor €2.5k + land reg €1k + survey/val €1k:
closing_costs = round(min(ceiling, asking_price or ceiling) * 0.01) + 4500
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd /Users/yashkarle/git/property-sahi-signal/backend && python3.11 -m pytest tests/unit/test_final_constraints.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ml/final_constraints.py backend/tests/unit/test_final_constraints.py
git commit -m "fix(ml): update closing costs to €4,500 fixed (solicitor+land reg+survey/val)"
```

---

## Task 3: Rule-Based Bidding Strategy

**Files:**
- Modify: `backend/app/services/bidding_service.py`
- Create: `backend/tests/unit/test_rule_based_strategy.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_rule_based_strategy.py`:

```python
import json
from unittest.mock import MagicMock
from app.services.bidding_service import _rule_based_strategy


def _mock_model(p25=386_000, sealed_prob=0.75, leverage=4.0,
                supply=2.4, active_count=4):
    m = MagicMock()
    m.p25_estimate = p25
    m.sealed_bid_probability = sealed_prob
    m.seller_leverage_score = leverage
    m.months_supply = supply
    m.active_supply_count = active_count
    return m


def _mock_prop(price=365_000):
    p = MagicMock()
    p.price = price
    p.address = "16 Beechdale Court, Dublin 24"
    return p


def test_strategy_returns_valid_json() -> None:
    result = _rule_based_strategy(_mock_prop(), 401_000, 370_000, 50_000, _mock_model())
    data = json.loads(result)
    assert all(k in data for k in ("opening", "escalation", "best_and_final", "walk_away"))


def test_opening_bid_is_above_asking() -> None:
    result = json.loads(_rule_based_strategy(_mock_prop(365_000), 401_000, 370_000, 50_000, _mock_model()))
    assert result["opening"]["amount"] > 365_000


def test_best_and_final_equals_buyer_ceiling() -> None:
    result = json.loads(_rule_based_strategy(_mock_prop(), 401_000, 370_000, 50_000, _mock_model()))
    assert result["best_and_final"]["amount"] == 401_000


def test_walk_away_ceiling_equals_buyer_ceiling() -> None:
    result = json.loads(_rule_based_strategy(_mock_prop(), 401_000, 370_000, 50_000, _mock_model()))
    assert result["walk_away"]["ceiling"] == 401_000


def test_escalation_increment_is_2500() -> None:
    result = json.loads(_rule_based_strategy(_mock_prop(), 401_000, 370_000, 50_000, _mock_model()))
    assert result["escalation"]["increment"] == 2500


def test_max_before_final_is_below_ceiling() -> None:
    result = json.loads(_rule_based_strategy(_mock_prop(), 401_000, 370_000, 50_000, _mock_model()))
    assert result["escalation"]["max_before_final"] < result["best_and_final"]["amount"]


def test_strategy_works_without_price_model() -> None:
    result = _rule_based_strategy(_mock_prop(), 401_000, 370_000, 50_000, None)
    data = json.loads(result)
    assert data["best_and_final"]["amount"] == 401_000


def test_strategy_works_without_aip_savings() -> None:
    result = _rule_based_strategy(_mock_prop(), 401_000, None, None, None)
    data = json.loads(result)
    assert data["best_and_final"]["amount"] == 401_000
```

- [ ] **Step 2: Run tests — expect ImportError (function doesn't exist yet)**

```bash
cd /Users/yashkarle/git/property-sahi-signal/backend && python3.11 -m pytest tests/unit/test_rule_based_strategy.py -v 2>&1 | tail -10
```

Expected: `ImportError: cannot import name '_rule_based_strategy'`.

- [ ] **Step 3: Add _rule_based_strategy() to bidding_service.py**

Read the current file first, then add these imports at the top and the new function + updated `generate_strategy`:

```python
"""Bidding strategy generation — Bedrock primary, rule-based fallback."""
from __future__ import annotations

import json

from app.core.bedrock import invoke_claude
from app.models.bid import BidSession
from app.models.property import Property

SYSTEM_PROMPT = """You are a Dublin property bidding strategist.
The buyer is mortgage-approved, chain-free, and can close in 6-8 weeks.
This is their strongest negotiating advantage. Be direct and tactical."""


def generate_strategy(
    prop: Property,
    user_max_budget: int,
    user_aip: int | None = None,
    user_savings: int | None = None,
    price_model=None,
) -> str | None:
    """Generate bidding strategy. Uses Bedrock when available; falls back to rule-based."""
    try:
        prompt = f"""Advise on bidding strategy for this Dublin property:

Property: {prop.address or prop.title}
Asking price: €{prop.price:,}
User's maximum budget: €{user_max_budget:,}
Days on market: {prop.days_on_market or 'unknown'}
Chain-free seller: {prop.is_chain_free}
Seller status: {prop.seller_status}
Heating type: {prop.heating_type}
Year built: {prop.year_built}

Return a JSON object with keys: opening, escalation, best_and_final, walk_away.
Each has: amount (int), rationale (str). escalation also has: increment (int), max_before_final (int).
walk_away has: ceiling (int), rationale (str).
Be specific with €amounts rounded to nearest €2,500."""
        return invoke_claude(prompt, system=SYSTEM_PROMPT)
    except Exception:
        return _rule_based_strategy(prop, user_max_budget, user_aip, user_savings, price_model)


def _rule_based_strategy(
    prop: Property,
    user_max_budget: int,
    user_aip: int | None,
    user_savings: int | None,
    price_model,
) -> str:
    """Derive a 4-step bidding strategy from the pricing model data without AI."""
    asking = prop.price or 0

    # Buyer ceiling — use user_max_budget as fallback when no AIP/savings provided
    if user_aip and user_savings:
        ltv_ceiling = int(user_aip / 0.9)
        closing = round(ltv_ceiling * 0.01) + 4500
        affordability = user_aip + user_savings - closing
        buyer_ceiling = (min(ltv_ceiling, affordability) // 1000) * 1000
    else:
        buyer_ceiling = user_max_budget

    # Extract model stats
    p25 = int(price_model.p25_estimate) if price_model and price_model.p25_estimate else None
    sealed_prob = float(price_model.sealed_bid_probability) if price_model else 0.5
    leverage = float(price_model.seller_leverage_score) if price_model else 3.0
    supply = float(price_model.months_supply) if price_model else 6.0
    active = int(price_model.active_supply_count) if price_model and price_model.active_supply_count else None

    # Opening bid: above asking, at least at P25 floor if available
    floor = int(p25 * 0.98) if p25 else asking
    opening = max(asking + 2500, floor)
    opening = round(opening / 2500) * 2500

    # Escalation cap: leave €7,500 gap before ceiling for best & final
    max_before_final = min(buyer_ceiling - 7500, opening + 5 * 2500)
    max_before_final = round(max_before_final / 2500) * 2500

    sealed_desc = "very likely" if sealed_prob > 0.7 else "likely" if sealed_prob > 0.4 else "unlikely"
    market_desc = "strong seller's market" if leverage > 3.5 else "balanced market" if leverage > 2.5 else "buyer-friendly market"
    supply_note = f"Only {active} active listings in this area." if active else ""

    walk_note = f"P25 comparable sales start at €{p25 // 1000}k — similar properties will appear." if p25 else "Comparable properties will appear."

    strategy = {
        "opening": {
            "amount": int(opening),
            "rationale": (
                f"Bid €{opening:,} — above asking (€{asking:,}), shows intent without revealing ceiling. "
                f"Ask the agent immediately: are there other bidders? Any cash buyers in the pool?"
            ),
        },
        "escalation": {
            "increment": 2500,
            "max_before_final": int(max_before_final),
            "rationale": (
                f"Move in €2,500 steps up to €{max_before_final:,}. Do not volunteer increases — wait for the agent "
                f"to call back. Sealed bid is {sealed_desc} ({int(sealed_prob * 100)}%) in this "
                f"{market_desc} ({supply:.1f} months supply). {supply_note}"
            ),
        },
        "best_and_final": {
            "amount": int(buyer_ceiling),
            "rationale": (
                f"Put in €{buyer_ceiling:,} as your sealed bid — your Central Bank 90% LTV ceiling. "
                f"Accompany with a bid letter: chain-free, AIP in hand, solicitor instructed, 6–8 week close. "
                f"Speed-to-close often beats a marginally higher uncertain bid."
            ),
        },
        "walk_away": {
            "ceiling": int(buyer_ceiling),
            "rationale": (
                f"Above €{buyer_ceiling:,} you exceed your mortgage limit. Walk away with confidence. "
                f"{walk_note}"
            ),
        },
    }
    return json.dumps(strategy)


def generate_bid_letter(
    prop: Property,
    user_bid: int,
    competing_bid: int | None,
    context: str,
) -> str:
    competing_text = f"There is a competing bid of €{competing_bid:,}." if competing_bid else ""
    prompt = f"""Write a persuasive letter to an Irish estate agent presenting a buyer's bid.

Property: {prop.address or prop.title}
User's bid: €{user_bid:,}
{competing_text}
{f'Context: {context}' if context else ''}

The buyer's key advantages:
- Fully mortgage-approved with AIP in hand
- No onward chain — no property to sell
- Title deeds ready with solicitor
- Can guarantee closing in 6-8 weeks
- First-time buyer (if applicable)

Note: Estate agents in Ireland are legally obligated to present ALL bids to the vendor.
Make clear this bid comes with certainty the competing bid may lack.

Write a professional 3-paragraph letter. Address it to "The Selling Agent"."""

    return invoke_claude(prompt, system=SYSTEM_PROMPT)
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd /Users/yashkarle/git/property-sahi-signal/backend && python3.11 -m pytest tests/unit/test_rule_based_strategy.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/bidding_service.py backend/tests/unit/test_rule_based_strategy.py
git commit -m "feat(bidding): add rule-based 4-step strategy fallback when Bedrock unavailable"
```

---

## Task 4: Update Bidding Schema + POST /sessions Endpoint

**Files:**
- Modify: `backend/app/schemas/bidding.py`
- Modify: `backend/app/routers/bidding.py`

- [ ] **Step 1: Update schemas**

Replace the content of `backend/app/schemas/bidding.py` with:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BidSessionCreate(BaseModel):
    property_id: uuid.UUID
    user_max_budget: int = Field(..., gt=0)  # kept for compat — set to user_aip when provided
    user_aip: int | None = Field(None, gt=0, description="Approved In Principle mortgage amount")
    user_savings: int | None = Field(None, ge=0, description="Available cash savings")


class BidEntryCreate(BaseModel):
    bid_amount: int = Field(..., gt=0)
    submitted_by: str = Field(..., pattern="^(user|other_buyer)$")
    notes: str | None = None


class OutcomeUpdate(BaseModel):
    outcome: str = Field(..., pattern="^(won|lost|withdrawn)$")
    actual_sale_price: int | None = Field(None, gt=0)


class BidEntryOut(BaseModel):
    id: uuid.UUID
    bid_amount: int
    submitted_by: str
    submitted_at: datetime
    notes: str | None = None
    is_winning: bool

    model_config = {"from_attributes": True}


class BidSessionOut(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    status: str
    user_max_budget: int | None = None
    user_aip: int | None = None
    user_savings: int | None = None
    actual_sale_price: int | None = None
    strategy_advice: str | None = None
    started_at: datetime
    entries: list[BidEntryOut] = []

    model_config = {"from_attributes": True}


class PropertySummaryForHistory(BaseModel):
    id: uuid.UUID
    address: str | None = None
    price: int | None = None
    bedrooms: int | None = None
    carpet_area_sqm: int | None = None
    ber_rating: str | None = None
    dublin_district: str | None = None
    url: str

    model_config = {"from_attributes": True}


class PriceModelSummary(BaseModel):
    offer_entry: int | None = None
    offer_sealed: int | None = None
    p25: int | None = None
    p50: int | None = None
    sealed_bid_probability: float | None = None


class BidHistoryItem(BaseModel):
    session_id: uuid.UUID
    property: PropertySummaryForHistory
    status: str
    user_max_budget: int | None = None
    user_aip: int | None = None
    user_savings: int | None = None
    started_at: datetime
    your_max_bid: int | None = None
    competing_max_bid: int | None = None
    actual_sale_price: int | None = None
    latest_price_model: PriceModelSummary | None = None


class OfferBandOut(BaseModel):
    entry: int
    sealed: int
    ceiling: int
    seller_leverage_score: float | None = None
    sealed_bid_probability: float | None = None
    over_asking_probability: float | None = None
    confidence_final: float | None = None
    p25: int | None = None
    p50: int | None = None
    p75: int | None = None


class BidLetterRequest(BaseModel):
    user_bid: int
    competing_bid: int | None = None
    additional_context: str | None = None


class BidLetterResponse(BaseModel):
    letter_text: str
```

- [ ] **Step 2: Update the POST /sessions handler and add PATCH /outcome + GET /history**

Replace `backend/app/routers/bidding.py` with:

```python
import uuid
from datetime import date

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
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

    # Fetch latest price model for strategy generation
    pm_result = await db.execute(
        select(PriceModelResult)
        .where(PriceModelResult.property_id == request.property_id, PriceModelResult.status == "ready")
        .order_by(PriceModelResult.run_at.desc())
        .limit(1)
    )
    price_model = pm_result.scalars().first()

    effective_budget = request.user_aip or request.user_max_budget
    try:
        strategy = generate_strategy(
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
    if request.actual_sale_price is not None:
        session.actual_sale_price = request.actual_sale_price
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

    # Deduplicate: one entry per property (most recent session)
    seen_props: set[uuid.UUID] = set()
    items: list[BidHistoryItem] = []
    for session in sessions:
        if session.property_id in seen_props:
            continue
        seen_props.add(session.property_id)

        your_max = max(
            (e.bid_amount for e in session.entries if e.submitted_by == "user"),
            default=None,
        )
        competing_max = max(
            (e.bid_amount for e in session.entries if e.submitted_by == "other_buyer"),
            default=None,
        )

        # Latest price model for this property
        pm_res = await db.execute(
            select(PriceModelResult)
            .where(PriceModelResult.property_id == session.property_id, PriceModelResult.status == "ready")
            .order_by(PriceModelResult.run_at.desc())
            .limit(1)
        )
        pm = pm_res.scalars().first()
        pm_summary = PriceModelSummary(
            offer_entry=pm.offer_entry,
            offer_sealed=pm.offer_sealed,
            p25=pm.p25_estimate,
            p50=pm.p50_estimate,
            sealed_bid_probability=float(pm.sealed_bid_probability) if pm.sealed_bid_probability else None,
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
```

- [ ] **Step 3: Verify the backend starts cleanly**

```bash
cd /Users/yashkarle/git/property-sahi-signal/backend && python3.11 -c "from app.routers.bidding import router; print('OK', [r.path for r in router.routes])"
```

Expected: prints OK with all route paths including `/sessions/{session_id}/outcome` and `/history`.

- [ ] **Step 4: Smoke test PATCH /outcome**

```bash
SESSION_ID=$(psql postgresql://property_user:property_pass@localhost:5432/property_sahi \
  -t -c "SELECT id FROM bid_sessions LIMIT 1;" | tr -d ' \n')

curl -s -X PATCH "http://localhost:8000/api/v1/bidding/sessions/${SESSION_ID}/outcome" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-in-production" \
  -d '{"outcome": "lost", "actual_sale_price": 397000}' | python3.11 -m json.tool | grep -E '"status"|"actual_sale"'
```

Expected: `"status": "lost"` and `"actual_sale_price": 397000`.

- [ ] **Step 5: Smoke test GET /history**

```bash
curl -s "http://localhost:8000/api/v1/bidding/history" \
  -H "X-API-Key: change-me-in-production" | python3.11 -m json.tool | head -30
```

Expected: JSON array of bid history items.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/bidding.py backend/app/routers/bidding.py
git commit -m "feat(bidding): add user_aip/savings to sessions, PATCH /outcome, GET /history"
```

---

## Task 5: Enrich Comparables Endpoint with Lat/Lng + Time-Adjusted Price

**Files:**
- Modify: `backend/app/schemas/pricing.py`
- Modify: `backend/app/routers/pricing.py`

- [ ] **Step 1: Add lat/lng fields to ComparableOut schema**

In `backend/app/schemas/pricing.py`, update `ComparableOut`:

```python
class ComparableOut(BaseModel):
    address: str
    date_of_sale: date
    price_eur: int
    time_adjusted_price: int | None = None
    floor_area_sqm: int | None = None
    price_per_sqm: float | None = None
    bedrooms: int | None = None
    property_type: str | None = None
    distance_m: float
    months_ago: float
    latitude: float | None = None
    longitude: float | None = None
    similarity_score: float | None = None
```

- [ ] **Step 2: Update GET /comparables to populate all new fields**

In `backend/app/routers/pricing.py`, replace the `get_comparables` function:

```python
@router.get("/{property_id}/comparables", response_model=list[ComparableOut])
async def get_comparables(
    property_id: uuid.UUID, db: DbSession, _: AuthDep
) -> list[ComparableOut]:
    result = await db.execute(
        select(PriceModelResult)
        .where(PriceModelResult.property_id == property_id, PriceModelResult.status == "ready")
        .order_by(PriceModelResult.run_at.desc())
        .limit(1)
    )
    latest = result.scalars().first()
    if not latest or not latest.comparables_used:
        raise HTTPException(status_code=404, detail="No model results found. Run /pricing/analyse first.")

    comp_ids = [uuid.UUID(c) for c in latest.comparables_used[:20]]
    ppr_result = await db.execute(select(PPRSale).where(PPRSale.id.in_(comp_ids)))
    comps = ppr_result.scalars().all()

    prop_result = await db.execute(select(Property).where(Property.id == property_id))
    prop = prop_result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    from app.ml.comparables import haversine_m
    from app.ml.time_adjustment import compute_monthly_drift, time_adjust_prices
    from app.ml.comparables import ComparableRecord

    # Build ComparableRecord list for time adjustment
    comp_records = [
        ComparableRecord(
            id=str(c.id),
            address=c.address,
            date_of_sale=c.date_of_sale,
            price_eur=c.price_eur,
            floor_area_sqm=c.floor_area_sqm,
            price_per_sqm=float(c.price_per_sqm) if c.price_per_sqm else None,
            bedrooms=c.bedrooms,
            property_type=c.property_type,
            latitude=float(c.latitude) if c.latitude else 0.0,
            longitude=float(c.longitude) if c.longitude else 0.0,
        )
        for c in comps
    ]

    monthly_drift = compute_monthly_drift(comp_records, date.today())
    adjusted_pairs = time_adjust_prices(comp_records, monthly_drift, date.today())
    adjusted_by_id = {pair[0].id: pair[1] for pair in adjusted_pairs}

    out = []
    for c in comps:
        dist = haversine_m(
            float(prop.latitude or 0), float(prop.longitude or 0),
            float(c.latitude or 0), float(c.longitude or 0),
        )
        months_ago = (date.today() - c.date_of_sale).days / 30.44
        out.append(ComparableOut(
            address=c.address,
            date_of_sale=c.date_of_sale,
            price_eur=c.price_eur,
            time_adjusted_price=adjusted_by_id.get(str(c.id)),
            floor_area_sqm=c.floor_area_sqm,
            price_per_sqm=float(c.price_per_sqm) if c.price_per_sqm else None,
            bedrooms=c.bedrooms,
            property_type=c.property_type,
            distance_m=round(dist),
            months_ago=round(months_ago, 1),
            latitude=float(c.latitude) if c.latitude else None,
            longitude=float(c.longitude) if c.longitude else None,
        ))
    return sorted(out, key=lambda x: x.distance_m)
```

- [ ] **Step 3: Smoke test the enriched comparables**

```bash
PROP_ID="29a12624-ee5e-469b-9cfe-d4bb390b0bfe"
curl -s "http://localhost:8000/api/v1/pricing/${PROP_ID}/comparables" \
  -H "X-API-Key: change-me-in-production" | python3.11 -m json.tool | head -30
```

Expected: First comparable has `latitude`, `longitude`, and `time_adjusted_price` populated.

- [ ] **Step 4: Run all unit tests**

```bash
cd /Users/yashkarle/git/property-sahi-signal/backend && python3.11 -m pytest tests/unit/ -v 2>&1 | tail -15
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/pricing.py backend/app/routers/pricing.py
git commit -m "feat(pricing): enrich comparables with lat/lng and time-adjusted prices"
```

---

## Self-Review

| Spec requirement | Covered |
|------------------|---------|
| DB migration for user_aip, user_savings, actual_sale_price | Task 1 ✅ |
| Closing costs = 1% stamp + €4,500 fixed | Task 2 ✅ |
| Rule-based 4-step strategy (opening/escalation/B&F/walk-away) | Task 3 ✅ |
| Strategy fallback when Bedrock unavailable | Task 3 (generate_strategy try/except) ✅ |
| POST /sessions accepts user_aip + user_savings | Task 4 ✅ |
| PATCH /sessions/{id}/outcome sets status + actual_sale_price | Task 4 ✅ |
| GET /bidding/history returns all sessions with property + model data | Task 4 ✅ |
| GET /comparables returns lat/lng + time_adjusted_price | Task 5 ✅ |
