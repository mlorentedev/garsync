# =============================================================================
# Makefile – Bootstrap, quality checks, and development shortcuts
# =============================================================================

SHELL := /bin/bash
.SHELLFLAGS := -c -o pipefail

POETRY ?= poetry
DAYS ?= 7
SMOKE_PORT ?= 8099

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
	@echo "  make setup              Install all dependencies (Python + Frontend)"
	@echo ""
	@echo "Quality:"
	@echo "  make check              Run ALL checks (backend + frontend)"
	@echo "  make smoke              E2E smoke test — start API, hit all endpoints"
	@echo "  make lint               Ruff linting (check only)"
	@echo "  make format             Ruff formatting + import sorting (auto-fix)"
	@echo "  make type               Mypy strict type checking"
	@echo "  make test               Run pytest suite"
	@echo "  make test-cov           Run pytest with coverage report"
	@echo "  make frontend-check     Astro type check + production build"
	@echo ""
	@echo "Development:"
	@echo "  make dev                Start FastAPI dev server (uvicorn, auto-reload)"
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
.PHONY: setup setup-python setup-poetry setup-dependencies setup-sops setup-data setup-frontend
setup: setup-python setup-poetry setup-dependencies setup-sops setup-data setup-frontend
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
	@$(POETRY) install --quiet

setup-sops:
	@if ! command -v sops >/dev/null 2>&1; then \
		echo "Warning: sops not found — secrets management unavailable"; \
	fi

setup-data:
	@mkdir -p data
	@if [ ! -f secrets.env.enc ]; then \
		echo "No secrets found. Use 'make secrets-edit' after creating secrets.env.enc"; \
	fi

setup-frontend:
	@cd frontend && npm install --silent

# -----------------------------------------------------------------------------
# Quality
# -----------------------------------------------------------------------------
.PHONY: check lint format type test test-cov frontend-check

check: lint type test frontend-check
	@echo "✓ All checks passed"

lint:
	@printf "  lint ........... "
	@$(POETRY) run ruff check src/ tests/ --quiet
	@$(POETRY) run ruff format --check src/ tests/ --quiet
	@echo "ok"

format:
	@$(POETRY) run ruff check --select I --fix src/ tests/
	@$(POETRY) run ruff format src/ tests/

type:
	@printf "  type ........... "
	@$(POETRY) run mypy --strict src/garsync/ > /dev/null
	@echo "ok"

test:
	@printf "  test ........... "
	@$(POETRY) run pytest --no-header --tb=short -W ignore::DeprecationWarning 2>&1 | tail -1


test-cov:
	@$(POETRY) run pytest --cov=garsync --cov-report=term-missing -v

frontend-check:
	@printf "  astro-check .... "
	@cd frontend && npx astro check 2>/dev/null | grep -oP '\d+ errors' || echo "0 errors"
	@printf "  astro-build .... "
	@cd frontend && npm run build --silent > /dev/null 2>&1
	@echo "ok"

# -----------------------------------------------------------------------------
# E2E Smoke Test
# -----------------------------------------------------------------------------
.PHONY: smoke

smoke:
	@echo "=== Smoke Test ==="
	@echo ""
	@# --- Preconditions ---
	@if [ ! -f data/garsync.db ]; then \
		echo "✗ data/garsync.db not found — run 'make sync' first"; \
		exit 1; \
	fi
	@printf "  db exists ...... ok\n"
	@# --- Start API ---
	@GARSYNC_DB_PATH=data/garsync.db $(POETRY) run uvicorn garsync.api.main:app \
		--host 127.0.0.1 --port $(SMOKE_PORT) --log-level error &>/dev/null & \
		echo $$! > .smoke.pid
	@sleep 1
	@if ! kill -0 $$(cat .smoke.pid) 2>/dev/null; then \
		echo "✗ API failed to start"; \
		rm -f .smoke.pid; \
		exit 1; \
	fi
	@printf "  api start ...... ok (pid %s, port %s)\n" "$$(cat .smoke.pid)" "$(SMOKE_PORT)"
	@# --- Hit endpoints ---
	@_fail=0; \
	for ep in \
		"/api/sync/status" \
		"/api/activities?page=1&limit=2" \
		"/api/biometrics?start_date=2025-01-01&end_date=2026-12-31" \
		"/api/sleep?start_date=2025-01-01&end_date=2026-12-31" \
		"/api/stats/summary?period=month" \
		"/api/stats/heatmap" \
	; do \
		_name=$$(echo "$$ep" | sed 's/?.*//' | sed 's|/api/||'); \
		printf "  %-17s" "$$_name"; \
		_code=$$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$(SMOKE_PORT)$$ep"); \
		if [ "$$_code" = "200" ]; then \
			echo "ok"; \
		else \
			echo "FAIL (HTTP $$_code)"; \
			_fail=1; \
		fi; \
	done; \
	kill $$(cat .smoke.pid) 2>/dev/null; \
	rm -f .smoke.pid; \
	echo ""; \
	if [ "$$_fail" = "1" ]; then \
		echo "✗ Smoke test failed"; \
		exit 1; \
	fi
	@# --- Frontend build ---
	@printf "  frontend-build . "
	@cd frontend && npm run build --silent > /dev/null 2>&1
	@echo "ok"
	@printf "  index.html ..... "
	@if [ -f frontend/dist/index.html ]; then echo "ok"; else echo "FAIL"; exit 1; fi
	@echo ""
	@echo "✓ Smoke test passed"

# -----------------------------------------------------------------------------
# Development
# -----------------------------------------------------------------------------
.PHONY: dev frontend-dev frontend-build sync secrets-edit

dev:
	@GARSYNC_DB_PATH=data/garsync.db $(POETRY) run uvicorn garsync.api.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	@cd frontend && npm run dev

frontend-build:
	@cd frontend && npm run build

sync: setup-data
	@sops -d --input-type dotenv --output-type dotenv secrets.env.enc > .env.tmp
	@set -a && . .env.tmp && set +a && \
		$(POETRY) run garsync --days $(DAYS) --activities-limit 100 --db data/garsync.db --verbose || true
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
		--days $(DAYS) --activities-limit 100 --db /app/data/garsync.db --verbose || true
	@rm -f .env.tmp

shell: setup-data
	@docker compose run --rm --entrypoint bash garsync

clean:
	@docker compose down -v
	@rm -f data/*.json .env.tmp
