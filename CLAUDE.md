# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Property Sahi Signal** is a 6-stage Dublin property buying assistant for mortgage-approved buyers (AIP, ~€325k budget, D12/D6W focus areas). It consists of a FastAPI backend, React frontend, and an AWS Lambda ingestion pipeline.

## Commands

### Backend (from repo root)
```bash
make dev          # Start full stack via docker compose (Postgres, Redis, LocalStack, API)
make migrate      # Run Alembic migrations: cd backend && alembic upgrade head
make test         # Run pytest: cd backend && pytest -x -q
make lint         # Ruff check: backend app/ + ingestion/
make format       # Ruff format: backend app/ + ingestion/
make ingest       # Run ingestion pipeline locally: cd ingestion && python lambda_handler.py
make seed-professionals   # Seed solicitors/surveyors data
make backfill-embeddings  # Backfill Titan embeddings for all properties (requires real AWS)
```

**Single test:**
```bash
cd backend && pytest tests/unit/test_foo.py::test_bar -x -v
```

**Run backend without Docker (local dev):**
```bash
cd backend && uvicorn app.main:app --reload --port 8000
```
Redis and OpenSearch are optional — the app fails gracefully (cache silently skipped, search falls back to Postgres ILIKE).

**Local install gotcha:** `pymc==5.18.2` in `pyproject.toml` doesn't exist on PyPI and isn't actually imported (the PyMC model runs on a remote `dhub` service). Install the other deps directly, skip pymc.

### Frontend (from `frontend/`)
```bash
npm install
npm run dev       # Vite dev server on http://localhost:5173
npm run build     # tsc -b && vite build
npm run lint      # ESLint
```

### Database
```bash
# New migration
cd backend && alembic revision --autogenerate -m "description"
# Apply
cd backend && alembic upgrade head
# Rollback
cd backend && alembic downgrade -1
```

**Seed Dublin property data:**
```bash
cd backend && python ../scripts/seed_properties.py
```

## Architecture

### Backend (`backend/app/`)

**Entry point:** `main.py` — FastAPI app, CORS, request logging middleware, router registration at `/api/v1`.

**Layers:**
- `routers/` — HTTP layer only: parse request, call service, return response
- `services/` — business logic; all async, receive `AsyncSession` via DI
- `models/` — SQLAlchemy 2.0 ORM (`mapped_column`, `DeclarativeBase`)
- `schemas/` — Pydantic v2 request/response models
- `ml/` — BuyerEdge 14-step pricing pipeline (pure functions, no I/O)
- `agents/orchestrator.py` — Claude Bedrock chat orchestrator that routes to specialist sub-agents

**Core infrastructure (`core/`):**
- `database.py` — async SQLAlchemy engine + `AsyncSession` factory
- `cache.py` — Redis async with silent fallback on `ConnectionError`
- `opensearch.py` — async OpenSearch client, kNN HNSW index; auth via `RequestsAWSV4SignerAuth(credentials_obj, region, service)`
- `bedrock.py` — Bedrock invoke wrappers (sync and streaming)
- `embeddings.py` — Titan Embeddings v2 (1536-dim) text → vector

**Pydantic + SQLAlchemy relationships — critical pattern:** Any response schema whose field maps to an ORM relationship (e.g. `BidSessionOut.entries`, `PropertyDetail.neighbourhood_score`) requires `.options(selectinload(Model.relationship))` in the query before `Model.model_validate()`. Otherwise lazy-load fires outside the async context and raises `MissingGreenlet`. This includes rows returned immediately after `db.commit() + db.refresh()` — `refresh` doesn't load relationships.

**Bedrock without AWS creds:** `invoke_claude()` / `invoke_claude_streaming()` both raise when LocalStack isn't running and no real AWS creds are configured. Any router that calls them (currently `bidding.create_session` and `bidding.create_bid_letter`) should wrap the call in `try/except` and return `None` / a fallback string. Don't let Bedrock unavailability 500 the whole endpoint.

**Search strategy:** Try OpenSearch kNN → if OpenSearch/Bedrock unavailable, fall back to Postgres ILIKE across address/title/description/district/estate_agent.

**ML pipeline (`ml/`):** 14 steps — comparables → winsorisation → time_adjustment → similarity_scoring → distribution → supply_analysis → seller_leverage → subjective_adjustments → sealed_bid_prob → offer_band → final_constraints → confidence_scoring. Each step is a pure function.

**AIP constraint limitation:** `final_constraints.apply_final_constraints()` computes `buyer_ceiling = AIP + savings − closing_costs`, where `closing_costs = 1% × asking_price + €3,150`. It **does not enforce the Central Bank 10% minimum deposit rule** (max purchase = AIP / 0.9 for FTBs at 90% LTV). For Irish FTB advice, the true mortgage-enforceable ceiling is lower than the model reports when bid price significantly exceeds asking. Stamp duty is also calculated on asking, not bid price — underestimates at higher bids.

**ML pipeline limitation — competitor buyer type not modelled:** `sealed_bid_prob.py` and `offer_band.py` treat all competing bidders as equivalent. Observed 2026-04-24: a €397k cash bidder beat €401.5k FTB+chain-free+AIP on the same property — vendor chose speed-to-close over price. Mortgage-approved buyers need ~1–2% bid premium to overcome cash competition. Future enhancement: add a `cash_buyer_present` boolean input to `PricingAnalyseRequest` and thread it into `final_constraints.py` so the recommended ceiling widens when cash is in the pool.

**Config:** `config.py` (`pydantic-settings`, reads `.env`). Key defaults: `DATABASE_URL` postgres on localhost:5432, `REDIS_URL` localhost:6379, `USE_LOCALSTACK=True`, `OPENSEARCH_ENDPOINT` localhost:4566.

### Frontend (`frontend/src/`)

React 18 + TypeScript + Vite + Tailwind CSS. State: TanStack Query v5 (server) + Zustand (client). Routing: react-router-dom v6.

Pages map to the 6 buyer stages: `SearchPage` → `PropertyDetailPage` → `ViewingPrepPage` → `ComparisonPage` → `BiddingPage` → `FinancingPage`. Also `ProfessionalsPage`.

API calls go through `src/api/` using axios, proxied to `http://localhost:8000` in dev.

### Ingestion Pipeline (`ingestion/`)

AWS Lambda (`lambda_handler.py`) triggered by EventBridge every 6 hours. Uses raw `asyncpg` (not SQLAlchemy). Pipeline:
1. `scrapers/ppr_scraper.py` — downloads PPR CSV from data.gov.ie
2. `scrapers/daft_scraper.py` — Playwright scraper for Daft.ie listings
3. `parsers/property_parser.py` — detects heating type, BER, management fee, HTB eligibility
4. `parsers/ppr_parser.py` — derives Dublin district from eircode/suburb
5. `enrichment/ppr_enricher.py` — matches PPR sales to listings (eircode-exact or district+price±15%)
6. `enrichment/embedding_enricher.py` — Titan embed + upsert to OpenSearch
7. DB upsert via `ON CONFLICT (url) DO UPDATE` for properties; `ON CONFLICT (address, date_of_sale, price_eur) DO NOTHING` for PPR

**Run locally:** `DATABASE_URL=postgresql://... python ingestion/lambda_handler.py`

**PPR CSV encoding:** Real PPR files from propertypriceregister.ie are **cp1252**, not latin-1. The `€` symbol is byte `0x80`. Local files in `data/` must be opened with `encoding="cp1252"` — the column header `Price (€)` otherwise reads as garbage and dict-key lookups silently miss. `ingestion/scrapers/ppr_scraper.py` hardcodes `latin-1` which works when the HTTP server transcodes but breaks on local files.

### Infrastructure

`docker-compose.yml`: Postgres 15, Redis 7, LocalStack 3.4 (S3 + OpenSearch + SecretsManager), API with live reload.

Migrations: `backend/alembic/versions/` — two migrations: `001_initial_schema.py` (all tables), `002_ppr_dedup_constraint.py` (unique index on ppr_sales for idempotent ingestion).

**Important enum gotcha:** SQLAlchemy 2.0 auto-creates Postgres enums during `op.create_table`. Do not add explicit `op.execute("CREATE TYPE ...")` calls in migrations — they will conflict with SQLAlchemy's auto-creation.

**Enum value reference** (for seed scripts and manual SQL):
- `property_type_enum`: `apartment | duplex | house | own_door_apartment` (no `semi_detached`, no `terraced`)
- `heating_type_enum`: `gas | oil | electric_storage | heat_pump | unknown`
- `seller_status_enum`: `chain_free | turnkey | renting | living | unknown`
- `source_enum`: `daft | myhome | ppr`

`properties.id` has no default — must pass `gen_random_uuid()` explicitly in raw INSERTs.

## Key Domain Details

**Buyer persona hardcoded in orchestrator:** AIP mortgage, €325k budget (€375k stretch), chain-free, targeting D12 (Crumlin, Walkinstown, Perrystown) and D6W (Kimmage).

**Critical flags the system always surfaces:**
- Electric storage heating → strongly penalise
- Celtic Tiger era (2000–2008) apartments → fire safety risk
- Missing floor area → critical viewing priority
- Management fees > €2,000/yr → flag high

**HTB (Help to Buy) eligibility:** New builds ≤ €500k only.

## Development Notes

- Python 3.11+ required (pyproject.toml `requires-python = ">=3.11"`)
- Ruff line length: 100 chars
- `pytest-asyncio` with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed
- `testcontainers[postgresql]` available for integration tests that need a real DB
- `backend/tests/unit/` and `backend/tests/integration/` directories exist but are empty — tests need to be written
- The `backfill_embeddings.py` script requires real AWS credentials and a live OpenSearch endpoint
