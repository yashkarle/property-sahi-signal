.PHONY: dev test migrate ingest lint format help

help:
	@echo "Usage: make <target>"
	@echo "  dev      - Start local dev stack (docker compose up)"
	@echo "  migrate  - Run Alembic migrations"
	@echo "  test     - Run pytest suite"
	@echo "  ingest   - Run Daft + PPR ingestion (local)"
	@echo "  lint     - Run ruff linter"
	@echo "  format   - Run ruff formatter"

dev:
	docker compose up --build

migrate:
	cd backend && alembic upgrade head

test:
	cd backend && pytest -x -q

ingest:
	cd ingestion && python lambda_handler.py

lint:
	cd backend && ruff check app/
	cd ingestion && ruff check .

format:
	cd backend && ruff format app/
	cd ingestion && ruff format .

seed-professionals:
	cd backend && python ../scripts/seed_professionals.py

backfill-embeddings:
	cd backend && python ../scripts/backfill_embeddings.py
