SHELL := /bin/sh
FAERS_BATCH_SIZE ?= 5000

.PHONY: help install install-frontend lint format-check typecheck test migrate ingest-faers api web compose-config up down check

help:
	@echo "PharmaSense development commands"
	@echo "  make install           Install Python development dependencies"
	@echo "  make install-frontend  Install locked frontend dependencies"
	@echo "  make check             Run backend and frontend checks"
	@echo "  make migrate           Apply database migrations"
	@echo "  make ingest-faers      Resume the verified FDA 2023 Q4 database load"
	@echo "  make up                Start the Docker Compose stack"

install:
	python -m pip install -r requirements.lock
	python -m pip install --no-deps -e .

install-frontend:
	cd apps/web && pnpm install --frozen-lockfile

lint:
	python -m ruff check .
	cd apps/web && pnpm lint

format-check:
	python -m ruff format --check .

typecheck:
	python -m mypy
	cd apps/web && pnpm typecheck

test:
	python -m pytest --cov --cov-report=term-missing
	cd apps/web && pnpm test

migrate:
	python -m alembic upgrade head

ingest-faers:
	python -m pharmasense.ingestion.faers.ingest_cli \
		data/raw/faers/2023Q4/faers_ascii_2023Q4.zip \
		--manifest docs/data-sources/manifests/faers-2023q4-ascii.json \
		--year 2023 --quarter 4 --batch-size $(FAERS_BATCH_SIZE) \
		--json-report data/processed/faers/2023Q4/ingestion-reconciliation.json \
		--markdown-report data/processed/faers/2023Q4/ingestion-reconciliation.md

api:
	python -m uvicorn pharmasense.api.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd apps/web && pnpm dev

compose-config:
	docker compose config --quiet

up:
	docker compose up --build

down:
	docker compose down

check: lint format-check typecheck test
