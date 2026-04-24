.PHONY: dev test migrate ingest lint format install seed-professionals seed-properties backfill-embeddings help

help:
	@echo "Usage: make <target>"
	@echo "  install              - Install all Python dependencies"
	@echo "  dev                  - Start local dev stack (docker compose up)"
	@echo "  migrate              - Run Alembic migrations"
	@echo "  test                 - Run pytest suite"
	@echo "  ingest               - Run Daft + PPR ingestion (local)"
	@echo "  seed-properties      - Seed 22 Dublin properties into Postgres"
	@echo "  seed-professionals   - Seed solicitors + surveyors into Postgres"
	@echo "  backfill-embeddings  - Compute Titan embeddings → OpenSearch"
	@echo "  lint                 - Run ruff linter"
	@echo "  format               - Run ruff formatter"

install:
	pip install -e "backend/[dev]"
	pip install -r ingestion/requirements.txt
	pip install -r scripts/requirements.txt
	playwright install chromium

dev:
	docker compose up --build

migrate:
	cd backend && alembic upgrade head

test:
	cd backend && pytest -x -q

ingest:
	cd ingestion && python lambda_handler.py

seed-properties:
	python scripts/seed_properties.py

seed-professionals:
	python scripts/seed_professionals.py

backfill-embeddings:
	python scripts/backfill_embeddings.py

lint:
	cd backend && ruff check app/
	cd ingestion && ruff check .

format:
	cd backend && ruff format app/
	cd ingestion && ruff format .
