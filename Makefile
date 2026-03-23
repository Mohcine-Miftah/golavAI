.PHONY: dev up down logs migrate seed test lint fmt

# ── Local development (without Docker) ──────────────────────
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	celery -A app.workers.celery_app worker --loglevel=info -Q ai,outbox,maintenance -c 4

beat:
	celery -A app.workers.celery_app beat --loglevel=info

# ── Docker Compose ───────────────────────────────────────────
up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

logs:
	docker-compose logs -f app worker beat

# ── Database ─────────────────────────────────────────────────
migrate:
	alembic upgrade head

migration:
	@read -p "Migration message: " msg; alembic revision --autogenerate -m "$$msg"

seed:
	python scripts/seed.py

# ── Tests ────────────────────────────────────────────────────
test:
	pytest app/tests/ -v --tb=short

test-unit:
	pytest app/tests/unit/ -v

test-integration:
	pytest app/tests/integration/ -v

cov:
	pytest app/tests/ --cov=app --cov-report=term-missing --cov-report=html

# ── Code quality ─────────────────────────────────────────────
lint:
	ruff check app/ scripts/

fmt:
	ruff format app/ scripts/

type-check:
	mypy app/

# ── Export ───────────────────────────────────────────────────
export-today:
	python scripts/export_today.py

# ── Setup ────────────────────────────────────────────────────
install:
	pip install -e ".[dev]"

env:
	cp .env.example .env
	@echo "✅ .env created — fill in your secrets before running"
