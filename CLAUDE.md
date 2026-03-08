# CLAUDE.md — GarSync Project Context

> **ROLE:** Senior Full-Stack Engineer.
> **CONTEXT:** Garmin fitness data pipeline and interactive dashboard.

## 🛠 Tech Stack
- **Backend:** Python 3.12, FastAPI, Pydantic v2.
- **Database:** SQLite (WAL mode).
- **Frontend:** Astro (Islands Architecture), Tailwind CSS, Chart.js.
- **Tooling:** Poetry, Ruff, mypy --strict, pytest.
- **Infra:** Docker Compose, SOPS + Age (secrets).

## 📁 Key Paths
- `src/garsync/`: Python source code.
  - `api/`: FastAPI routes and application factory.
  - `db/`: Repository layer and SQLite schema.
  - `cli.py`: Typer-based sync pipeline.
- `frontend/`: Astro project.
  - `src/components/`: Dashboard UI components.
  - `src/lib/api.ts`: TypeScript fetch wrappers.
- `tests/`: Test suite (backend + integration).
- `docs/`: Deployment and usage guides.

## 🚀 Key Commands
- `make setup`: Bootstrap environment (Python + Node).
- `make sync DAYS=7`: Pull data from Garmin Connect (requires SOPS key).
- `make dev`: Start both API (8000) and Frontend (4321) with hot-reload.
- `make check`: Run all quality checks (lint, type, test).
- `make build`: Build Docker image.
- `make run`: Start production container.
- `make smoke`: Run E2E smoke tests.

## 💡 Development Rules
- **TDD:** New features/fixes MUST have tests in `tests/`.
- **Validation:** Run `make check` before proposing any PR.
- **Data Safety:** Never commit unencrypted secrets. Use SOPS.
- **Consistency:** Follow existing repository patterns for SQLite access.
- **UI:** Prefer vanilla CSS or Tailwind; avoid external component libraries.
