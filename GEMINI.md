# GEMINI.md — GarSync Project Instructions

> **ROLE:** Senior Full-Stack Engineer.
> **CONTEXT:** Fitness data pipeline (Garmin Connect → SQLite → FastAPI → Astro).
> **GOAL:** Finish Sprint 4 (Integration + Deploy) and professionalize the repo for v1.0.

## 1. Technical Standards

### Python (Backend)
- **Version:** 3.12+ (Strict)
- **Framework:** FastAPI + Pydantic v2
- **Persistence:** SQLite (WAL mode enabled)
- **Tools:** Poetry, Ruff (lint/format), mypy --strict, pytest
- **Commands:** `make test-backend`, `make lint-backend`

### Astro (Frontend)
- **Version:** Latest (Islands Architecture)
- **Styling:** Tailwind CSS (v3/v4 as per config)
- **State:** Nano Stores
- **Components:** Chart.js for visualizations
- **Commands:** `npm run dev`, `npm run build` (inside `/frontend`)

### Infrastructure
- **Deployment:** Docker Compose (API + Astro + SQLite volume)
- **Secrets:** SOPS + AGE (do NOT touch `.sops.yaml` or encrypted files unless asked)

## 2. Development Workflow

1. **Research:** Check `10_projects/garsync/` in Hive Vault for tasks and lessons before acting.
2. **Execution:**
   - **TDD:** Write/update tests in `tests/` before modifying logic.
   - **Validation:** Run `make check` (must include backend lint/test + frontend build).
3. **Knowledge Loop:**
   - Capture non-trivial bugs/fixes in `90-lessons.md`.
   - Document architectural changes in `30-architecture/adr-XXX.md`.
   - Update `11-tasks.md` progress bar after each task.

## 3. Critical Constraints

- **Data Integrity:** Garmin API responses are inconsistent. Always use `.get()` with defaults and handle both list/dict formats (Ref: Lesson L-001).
- **Silent Errors:** Never use bare `catch {}` in Astro scripts. Use `console.error` and avoid variable name collisions with DOM elements (Ref: Lesson L-003).
- **Context Window:** When summarizing data for AI insights, be efficient with token usage.

## 4. Key Paths

- **Backend:** `src/garsync/`
- **Frontend:** `frontend/`
- **Tests:** `tests/`
- **Vault:** `10_projects/garsync/` (Strategic Context)
