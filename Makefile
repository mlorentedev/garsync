# =============================================================================
# Makefile – Bootstrap, quality checks, and development shortcuts
# =============================================================================

SHELL := /bin/bash
.SHELLFLAGS := -c -o pipefail

POETRY ?= poetry
PYTHON_VERSION ?= 3.12
DAYS ?= 7

export SOPS_AGE_KEY_FILE ?= /home/manu/.config/age/key.txt

.DEFAULT_GOAL := help

# -----------------------------------------------------------------------------
# Help
# -----------------------------------------------------------------------------
.PHONY: help
help:
	@echo "=== GarSync ==="
	@echo ""
	@echo "Bootstrap:"
	@echo "  make setup              Install Poetry, dependencies, create data dir"
	@echo ""
	@echo "Quality:"
	@echo "  make check              Run all checks (lint + type + test)"
	@echo "  make lint               Ruff linting (check only)"
	@echo "  make format             Ruff formatting + import sorting (auto-fix)"
	@echo "  make type               Mypy strict type checking"
	@echo "  make test               Run pytest suite"
	@echo "  make test-cov           Run pytest with coverage report"
	@echo ""
	@echo "Development:"
	@echo "  make dev                Start FastAPI dev server (uvicorn, auto-reload)"
	@echo "  make frontend-setup     Install frontend (Astro) dependencies"
	@echo "  make frontend-dev       Start Astro dev server (port 4321)"
	@echo "  make frontend-build     Build Astro static site to frontend/dist/"
	@echo "  make sync DAYS=7        Run Garmin sync to SQLite (requires secrets)"
	@echo "  make secrets-edit       Edit SOPS-encrypted secrets"
	@echo ""
	@echo "Docker:"
	@echo "  make build              Build Docker image"
	@echo "  make run DAYS=7         Run sync via Docker (requires secrets)"
	@echo "  make shell              Open shell in Docker container"
	@echo "  make clean              Stop containers and remove data"
	@echo ""

# -----------------------------------------------------------------------------
# Bootstrap
# -----------------------------------------------------------------------------
.PHONY: setup setup-python setup-poetry setup-dependencies setup-sops setup-data
setup: setup-python setup-poetry setup-dependencies setup-sops setup-data
	@echo "✓ Setup complete"

setup-python:
	@if ! command -v python3 >/dev/null 2>&1; then \
		echo "Error: Python 3 is required"; \
		exit 1; \
	fi

setup-poetry:
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "Installing Poetry..."; \
		python3 -m pip install --upgrade poetry >/dev/null 2>&1; \
	fi
	@$(POETRY) config virtualenvs.create true
	@$(POETRY) config virtualenvs.in-project true

setup-dependencies:
	@$(POETRY) install

setup-sops:
	@if ! command -v sops >/dev/null 2>&1; then \
		echo "Warning: sops not found — secrets management unavailable"; \
	fi

setup-data:
	@mkdir -p data
	@if [ ! -f secrets.env.enc ]; then \
		echo "No secrets found. Use 'make secrets-edit' after creating secrets.env.enc"; \
	fi

# -----------------------------------------------------------------------------
# Quality
# -----------------------------------------------------------------------------
.PHONY: check lint format type test test-cov

check: lint type test
	@echo "✓ All checks passed"

lint:
	@$(POETRY) run ruff check src/ tests/
	@$(POETRY) run ruff format --check src/ tests/

format:
	@$(POETRY) run ruff check --select I --fix src/ tests/
	@$(POETRY) run ruff format src/ tests/

type:
	@$(POETRY) run mypy --strict src/garsync/

test:
	@$(POETRY) run pytest

test-cov:
	@$(POETRY) run pytest --cov=garsync --cov-report=term-missing -v

# -----------------------------------------------------------------------------
# Development
# -----------------------------------------------------------------------------
.PHONY: dev frontend-setup frontend-dev frontend-build sync secrets-edit

dev:
	@GARSYNC_DB_PATH=data/garsync.db $(POETRY) run uvicorn garsync.api.main:app --reload --host 0.0.0.0 --port 8000

frontend-setup:
	@cd frontend && npm install

frontend-dev:
	@cd frontend && npm run dev

frontend-build:
	@cd frontend && npm run build

sync: setup-data
	@sops -d --input-type dotenv --output-type dotenv secrets.env.enc > .env.tmp
	@set -a && . .env.tmp && set +a && \
		$(POETRY) run garsync --days $(DAYS) --activities-limit 10 --db data/garsync.db --verbose || true
	@rm -f .env.tmp

secrets-edit:
	@sops --input-type dotenv --output-type dotenv secrets.env.enc || true

# -----------------------------------------------------------------------------
# Docker
# -----------------------------------------------------------------------------
.PHONY: build run shell clean

build:
	@docker compose build

run: setup-data
	@sops -d --input-type dotenv --output-type dotenv secrets.env.enc > .env.tmp
	@docker compose run --rm --env-from-file .env.tmp garsync \
		--days $(DAYS) --activities-limit 10 --db /app/data/garsync.db --verbose || true
	@rm -f .env.tmp

shell: setup-data
	@docker compose run --rm --entrypoint bash garsync

clean:
	@docker compose down -v
	@rm -f data/*.json .env.tmp
