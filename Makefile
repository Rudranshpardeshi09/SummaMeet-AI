.PHONY: help install dev infra infra-down db-migrate db-seed api bot-worker transcription-worker flower lint format typecheck test clean keys

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ---- Setup ----

install: ## Install all workspace dependencies with uv
	uv sync --all-packages

keys: ## Generate RSA key pair for JWT signing
	@mkdir -p jwt_keys
	openssl genrsa -out jwt_keys/jwt_private.pem 2048
	openssl rsa -in jwt_keys/jwt_private.pem -pubout -out jwt_keys/jwt_public.pem
	@echo "✓ JWT keys generated in jwt_keys/"

env: ## Copy .env.example to .env
	@cp -n .env.example .env 2>/dev/null || echo ".env already exists"
	@echo "✓ Environment file ready. Edit .env with your values."

# ---- Infrastructure ----

infra: ## Start PostgreSQL, Redis, and MinIO containers
	docker compose up -d
	@echo "✓ Infrastructure services started"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  Redis:      localhost:6379"
	@echo "  MinIO API:  localhost:9000"
	@echo "  MinIO UI:   localhost:9001"

infra-down: ## Stop all infrastructure containers
	docker compose down

infra-reset: ## Stop containers and delete all data volumes
	docker compose down -v
	@echo "✓ All data volumes deleted"

# ---- Database ----

db-migrate: ## Generate a new Alembic migration (usage: make db-migrate msg="add users table")
	cd apps/api && alembic revision --autogenerate -m "$(msg)"

db-upgrade: ## Apply all pending migrations
	cd apps/api && alembic upgrade head

db-downgrade: ## Rollback last migration
	cd apps/api && alembic downgrade -1

db-seed: ## Seed the database with initial org + admin user + API keys
	cd apps/api && python -m app.db.seed

# ---- Development Servers ----

api: ## Start FastAPI dev server with hot reload
	cd apps/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

api-scheduler: ## Start Celery beat scheduler for API
	cd apps/api && celery -A app.core.celery.celery_app beat --loglevel=info

bot-worker: ## Start bot worker (Celery) — joins Google Meet sessions
	cd apps/bot_worker && celery -A bot_worker.celery_app worker -Q bot -c 1 --loglevel=info -n bot@%h

transcription-worker: ## Start transcription worker (Celery) — local Whisper STT
	cd apps/transcription_worker && celery -A transcription_worker.celery_app worker -Q transcription -c 1 --loglevel=info -n transcription@%h

summarization-worker: ## Start summarization worker (Celery) — OpenAI integration
	cd apps/summarization_worker && celery -A summarization_worker.celery_app worker -Q summarization -c 1 --loglevel=info -n summarization@%h

flower: ## Start Celery Flower monitoring UI (http://localhost:5555)
	celery -A bot_worker.celery_app flower --port=5555

# ---- Code Quality ----

lint: ## Run ruff linter on all packages
	uv run ruff check .

format: ## Format code with black
	uv run black .

typecheck: ## Run mypy type checking
	uv run mypy apps/api/app --ignore-missing-imports

# ---- Testing ----

test: ## Run all tests with pytest
	uv run pytest -v

test-api: ## Run API tests only
	cd apps/api && uv run pytest -v

test-cov: ## Run tests with coverage report
	uv run pytest --cov=apps/api/app --cov-report=html

# ---- Cleanup ----

clean: ## Remove caches, build artifacts, and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage
	@echo "✓ Cleaned up caches and artifacts"
