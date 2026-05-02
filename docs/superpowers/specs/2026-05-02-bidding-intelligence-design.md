# Bidding Intelligence — Design Spec

**Status:** Approved · **Date:** 2026-05-02 · **Owner:** yashkarle

---

## Problem

The current bidding flow has four critical gaps:

1. **Ceiling calculation is broken** — `buyer_ceiling` is always null because `buyer_savings` is never captured. The offer band shows a €665k market ceiling that is meaningless and misleading for a buyer capped at ~€401k by the Central Bank 90% LTV rule.
2. **No market intelligence on the bidding page** — the pricing model produces rich data (P25/P50/P75, sealed-bid probability, seller leverage, 20 comparable sales with coordinates) but none of it is surfaced to the buyer in a usable way during an active bid.
3. **Financing and bidding are disconnected** — the financing page holds AIP + savings as local state that evaporates on navigation. These values must feed the bidding ceiling calculation.
4. **No outcome tracking or cross-property learning** — bid history is unrecorded, lost bids (including cash-buyer losses) leave no data trail, and there is no way to compare properties being actively bid on.

## Goal

Rebuild the bidding experience as a split-panel intelligence console. Surface real-time market data, enforce the buyer's true ceiling, generate a structured 4-step bidding strategy without requiring Bedrock, and track outcomes across properties so the buyer builds compounding knowledge over time.

---

## Scope

**In scope:**
- Global financial profile (AIP + savings + FTB flag) persisted in localStorage via Zustand middleware, pre-populating bidding + financing
- BiddingPage split-panel redesign (Layout C)
- 4-step rule-based bidding strategy (no Bedrock dependency)
- Comparables endpoint with buyer-specified filter (1km, 18mo, type ±match, beds ±1, size ±20%)
- Interactive scatter chart: time × adjusted sale price with reference lines (ceiling, asking, P25–P75 band)
- Leaflet map: comparable pins colour-coded by price vs buyer ceiling, 1km radius circle
- Outcome recording: Won / Lost / Withdrawn + actual sale price input
- `actual_sale_price` on `BidSession` — feeds back into comparables for nearby future analyses
- `/bid-history` page: all tracked properties, summary stats, inline comparison table for selected properties
- Rule-based comparison insight (no Bedrock) summarising key similarities and differences

**Out of scope:**
- Bedrock-based narrative generation (deferred — will work automatically once AWS creds are configured)
- Solicitor / agent contact management
- Push notifications for outbid events
- Historical price trend modelling using outcome data (phase 2)

---

## Ceiling Calculation

```
closing_costs = round(bid_price × 0.01)   # stamp duty 1%
              + 2500                        # solicitor
              + 1000                        # land registry
              + 1000                        # valuation + surveyor
              = round(bid_price × 0.01) + 4500

ltv_ceiling   = floor(aip / 0.9)           # Central Bank 90% LTV (FTB)

affordability = aip + savings - closing_costs(ltv_ceiling)

buyer_ceiling = min(ltv_ceiling, affordability)
              → rounded down to nearest €1,000
```

**Example (AIP €370k, savings €50k, FTB):**
- LTV ceiling: €411,111
- Closing at €411k: €4,110 stamp + €4,500 = €8,610
- Affordability: €370k + €50k − €8,610 = €411,390
- Binding ceiling: min(€411,111, €411,390) = **€411,111 → €411,000**

---

## Architecture

### New: `frontend/src/store/financialProfileStore.ts`

Zustand store with `persist` middleware → localStorage key `financial-profile`.

```typescript
interface FinancialProfile {
  aip: number           // Approved In Principle mortgage amount
  savings: number       // Available cash savings
  isFirstTimeBuyer: boolean
  // Derived (not stored — computed on read)
  // buyerCeiling(): number
}
```

`buyerCeiling(aip, savings, isFirstTimeBuyer)` is a pure function exported from this store file. The ceiling uses the formula above. Only FTBs are capped at 90% LTV; second-time buyers use 80% (AIP / 0.8).

### Modified: `frontend/src/store/sessionStore.ts`

Remove `activePropertyId` is already there. No change needed to session store structure — financial profile moves to its own store.

### Modified: `backend/app/models/bid.py`

Add two columns to `BidSession`:
- `user_aip: Mapped[int | None]` — AIP at session creation time
- `user_savings: Mapped[int | None]` — savings at session creation time
- `actual_sale_price: Mapped[int | None]` — recorded on outcome

Keep `user_max_budget` as-is for backward compatibility with existing rows.

### New: `backend/alembic/versions/003_bid_session_financial_fields.py`

```sql
ALTER TABLE bid_sessions
  ADD COLUMN user_aip INTEGER,
  ADD COLUMN user_savings INTEGER,
  ADD COLUMN actual_sale_price INTEGER;
```

### New: `backend/app/routers/ingest.py` (already exists) → no change

### New: `backend/app/routers/bidding.py` additions

**`POST /api/v1/bidding/sessions` — updated request schema**

Add `user_aip: int | None` and `user_savings: int | None` to `BidSessionCreate`. Keep `user_max_budget` as an alias (set it to `user_aip` when provided, for backward compat with existing frontend before this migration).

**`PATCH /api/v1/bidding/sessions/{session_id}/outcome`**

```
Request: { "outcome": "won" | "lost" | "withdrawn", "actual_sale_price": int | null }
Response: BidSessionOut
```

Sets `status` and `actual_sale_price` on the session.

**`GET /api/v1/bidding/history`**

Returns all bid sessions for the buyer (all, not filtered by property), joined with property data. Used by the history page.

```
Response: [
  {
    "session_id": "uuid",
    "property": { "id", "address", "price", "bedrooms", "carpet_area_sqm", "ber_rating", "dublin_district", "url" },
    "status": "active" | "won" | "lost" | "withdrawn",
    "user_max_budget": int,
    "user_aip": int | null,
    "user_savings": int | null,
    "started_at": datetime,
    "your_max_bid": int | null,        // max of user's own bid entries
    "competing_max_bid": int | null,   // max of other_buyer entries
    "actual_sale_price": int | null,
    "latest_price_model": { "offer_entry", "offer_sealed", "p25", "p50", "sealed_bid_probability" } | null
  }
]
```

### New: `backend/app/routers/pricing.py` addition

**`GET /api/v1/pricing/{property_id}/comparables`**

Returns the comparable sales used in the latest price model run, enriched with time and size adjustment factors. Used by the chart and map.

```
Response: {
  "property_id": "uuid",
  "subject": { "lat", "lng", "bedrooms", "carpet_area_sqm", "property_type" },
  "comparables": [
    {
      "id": "uuid",
      "address": str,
      "date_of_sale": date,
      "price_eur": int,
      "time_adjusted_price": int | null,
      "floor_area_sqm": int | null,
      "bedrooms": int | null,
      "property_type": str | null,
      "distance_m": float,
      "months_ago": float,
      "latitude": float,
      "longitude": float
    }
  ],
  "stats": { "p25": int, "p50": int, "p75": int, "n": int }
}
```

Filter logic (applied in the service): pull the `comparables_used` UUIDs from the latest `price_model_results` row. If none, run a fresh comparable search with: radius ≤ 1km, last 18 months, beds within ±1, size within ±20% (null size = include).

### Modified: `backend/app/ml/final_constraints.py`

Update closing costs formula:

```python
closing_costs = round(bid_price * 0.01) + 4500  # stamp 1% + solicitor 2.5k + land reg 1k + survey/val 1k
```

(Was: `round(price * 0.01) + 3150`)

### Modified: `backend/app/services/bidding_service.py`

Replace `generate_strategy()` with a rule-based fallback that fires when Bedrock is unavailable. The function signature stays the same; the implementation becomes:

```python
def generate_strategy(prop: Property, user_max_budget: int,
                      user_aip: int | None = None,
                      user_savings: int | None = None,
                      price_model: PriceModelResult | None = None) -> str | None:
    try:
        return invoke_claude(...)   # Bedrock path — unchanged
    except Exception:
        return _rule_based_strategy(prop, user_max_budget, user_aip, user_savings, price_model)
```

**`_rule_based_strategy()` output structure:**

The function returns a structured JSON string that the frontend renders as the 4-step card. Fields:

```json
{
  "opening": { "amount": 375000, "rationale": "..." },
  "escalation": { "increment": 2500, "max_before_final": 395000, "rationale": "..." },
  "best_and_final": { "amount": 401000, "rationale": "..." },
  "walk_away": { "ceiling": 401000, "rationale": "..." }
}
```

**Step derivation logic:**

| Step | Amount | Rule |
|------|--------|------|
| Opening | `max(asking_price + 2500, round(p25 * 0.98 / 2500) * 2500)` | Just above asking, not below P25 floor |
| Escalation increment | `2500` | Fixed |
| Max before final | `min(buyer_ceiling - 7500, opening + 5 * 2500)` | Leave room for best & final |
| Best & Final | `buyer_ceiling` | Hard ceiling |
| Walk-away | `buyer_ceiling` | Same — do not go above |

### New: `frontend/src/pages/BiddingPage.tsx` (full rewrite)

Split-panel layout (CSS Grid `420px 1fr`):

**Left panel (fixed width, scrollable):**
1. Property header bar (dark, address + asking)
2. Financial strip: AIP · Savings · Your ceiling (3 cells)
3. Warning banner — shown when `market_entry > buyer_ceiling`
4. Market signals (5 bar rows: sealed prob, leverage, over-asking prob, active supply, months supply)
5. Live bid ladder (reverse-chronological, streamed via 30s poll)
6. Log bid form (my bid / competing bid toggle + amount input + Log button)
7. Outcome recording (Won / Lost / Withdrawn buttons → amount input modal)

**Right panel (flexible, scrollable):**
1. Strategy panel — 4-step cards with numbered circles, rendered from `strategy_advice` JSON or rule-based fallback
2. Comparables scatter chart — `recharts ScatterChart`, x=date, y=time-adjusted price
   - Reference lines: buyer ceiling (red dashed), asking price (orange dashed)
   - Shaded band: P25–P75 (green, 8% opacity)
   - Dot colours: grey=outlier, green=within buyer ceiling, blue=last 6 months
   - Hover tooltip: address, price, date, distance
3. Leaflet map — `react-leaflet MapContainer`
   - Centre: subject property coordinates
   - Circle: 1km radius dashed
   - Subject pin: red
   - Comparable pins: same colour scheme as chart dots
   - Click pin → popup with address + price + date
4. Key insight box (green) — static text derived from model stats

### New: `frontend/src/pages/BidHistoryPage.tsx`

Route: `/bid-history`

**Sections:**
1. Summary stat bar (5 cells): properties tracked, active, won, lost, avg outcome vs ceiling
2. Property list — one card per session, columns: property, asking, your max bid, status badge, final price, compare toggle
3. Comparison table — shown when ≥2 properties selected via compare toggle
   - Rows: asking, your ceiling, beds/size, BER, sealed prob, leverage, supply, P25, ceiling vs P25, cash buyer risk, district
   - Colour coding: green/orange/red
   - AI insight paragraph at bottom (rule-based — compare key dimensions and surface the most important difference)

**Comparison insight rule logic:**
- If any session has `status = "lost"` and `actual_sale_price < your_max_bid` → flag cash buyer / speed risk
- If BER differs by ≥2 bands → flag energy cost difference
- If `sealed_bid_probability` differs by ≥20pp → flag market pressure difference
- Surface the 2 most important differences as a 3-sentence paragraph

### Modified: `frontend/src/App.tsx`

Add `/bid-history` route → `BidHistoryPage`.

Add "Bid History" nav link to the nav bar.

### Modified: `frontend/src/pages/FinancingPage.tsx`

Pre-populate `aip_amount` and `current_savings` from `financialProfileStore` instead of local state defaults. On change, write back to the store.

---

## Data Flow

```
User enters AIP + savings in BiddingPage session start form
  → saved to financialProfileStore (localStorage)
  → passed to POST /bidding/sessions as { user_aip, user_savings }
  → used in buyerCeiling() function (frontend, pure)
  → passed to POST /pricing/analyse as { buyer_aip, buyer_savings }
  → final_constraints.apply_final_constraints() computes buyer_ceiling
  → buyer_ceiling returned in price model result
  → GET /pricing/{id}/offer-band returns buyer_ceiling
  → shown in bid band UI

User clicks "Run Price Analysis"
  → POST /pricing/analyse (buyer_aip, buyer_savings from session/store)
  → strategy JSON written to bid_sessions.strategy_advice
  → GET /pricing/{id}/comparables fetched for chart + map
  → Chart and map render

User clicks "Won / Lost / Withdrawn"
  → PATCH /bidding/sessions/{id}/outcome { outcome, actual_sale_price }
  → bid_sessions.status + actual_sale_price updated
  → actual_sale_price available as a real data point for future nearby comparables
```

---

## Testing

**Unit:**
- `buyerCeiling()` pure function: FTB 90% cap, second-buyer 80% cap, closing cost formula
- `_rule_based_strategy()`: derive opening bid, escalation max, best & final from model data
- `_comparison_insight()`: cash buyer flag, BER gap, sealed-bid gap logic

**Integration:**
- `PATCH /outcome` sets status + actual_sale_price, returns updated session
- `GET /bid-history` returns all sessions joined with property + latest price model
- `GET /comparables` returns correct comparable set with distance + time adjustment fields

**Manual smoke:**
- Start session on 16 Beechdale Court (AIP €370k, savings €50k) → ceiling shows €411k
- Run price analysis → strategy JSON populated, chart + map render with 20 dots
- Log competing bid → ladder updates immediately (no 30s wait)
- Mark session Lost + enter €403k → shows in history page with outcome
- Select Beechdale + Old Court Lodge → comparison table renders, insight surfaces cash buyer risk

---

## Definition of Done

- Bidding page split panel renders correctly for an active property with a price model result
- `buyer_ceiling` is non-null and reflects Central Bank LTV cap + correct closing costs
- 4-step strategy renders from rule-based JSON when Bedrock is unavailable
- Scatter chart shows comparable dots with correct reference lines and P25–P75 band
- Leaflet map shows subject property + colour-coded comp pins within 1km circle
- Outcome recording (Won/Lost/Withdrawn + price) persists to `bid_sessions`
- `/bid-history` shows all tracked sessions with summary stats
- Comparison table renders for ≥2 selected properties with insight paragraph
- AIP + savings pre-populated in Financing page from shared store
- `make test` green, `make lint` clean
