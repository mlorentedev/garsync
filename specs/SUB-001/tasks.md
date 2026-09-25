---
tags: [spec, tasks, migrations, alembic]
created: "2026-09-24"
---

# Tasks - SUB-001

> TDD order. One task = one focused commit. Tick as you go. Frozen once `status: implementing`.
>
> **Inline markers:**
> - `[P]` — no dependency on another unchecked task; safe to batch or fan out. TDD chains (test → implement → refactor of the *same* behaviour) are sequential and must NOT carry `[P]`.
> - `[AC<n>]` — the acceptance criterion this task helps satisfy (deterministic coverage for `/spec check`).
>
> **Ordering is load-bearing and comes from the seam, not from taste.** `env.py` must hand Alembic the
> caller's connection *first*: every fixture in this suite builds a `:memory:` database, and a second
> connection to `:memory:` is a second empty database, so an Alembic that opens its own URL yields
> zero tables and the whole suite goes green against nothing. The backup target comes before any
> revision touches a file, and the real-database rehearsal comes *after* the fixtures pass.

## Setup

- [x] Branch from `master`: `feat/alembic-schema-migration` (ticket in the PR body, not in the branch name)
- [x] `proposal.md` complete, R1–R8 ruled, acceptance criteria testable
- [x] No open questions left in `proposal.md` "Risks / open questions"

## Implementation

### 1 — The seam: Alembic runs on the caller's connection

- [x] [AC1] Add `alembic` **and** `sqlalchemy` to Poetry dependencies (SQLAlchemy is imported directly by the Core ops, so it is declared, not inherited), with the dependency addition stated in the commit message
- [x] [AC1] Record the one friction this brings: `mypy --strict` over `alembic`/`sqlalchemy` imports — resolve with a typed `env.py` plus a stated `ignore_missing_imports` override, or exclude `migrations/` from the type target — and note which was chosen
- [x] [AC1] Write the failing seam test: `init_db(conn)` on a `:memory:` connection leaves an `alembic_version` row at head **and** every expected table present on *that same connection* (fails today: no `alembic_version`)
- [x] [AC1] `alembic.ini` at the repo root with an **empty** `sqlalchemy.url` — the URL is supplied at runtime, so no credential ever sits in a checked-in ini — and `script_location = src/garsync/db/migrations` so the revisions ship inside the package
- [x] [AC1] `migrations/env.py` that reads `cfg.attributes["connection"]` and refuses to fall back to a URL — **no `render_as_batch`**: the flag only shapes `--autogenerate`, and every batch op here is written explicitly
- [x] [AC1] Baseline revision `0001_v1` reproducing `_SCHEMA_V1` exactly (`render_as_batch` exercised, `schema_version` included so a legacy file can be stamped)
- [x] [AC1] Freeze the v1 DDL as a test fixture (`tests/fixtures/schema_v1.sql`) — a copy the migration's *from* state can be built from, so the migration test never depends on code that no longer exists
- [x] [AC1] `init_db(conn)` becomes `command.upgrade` over the caller's connection; `CURRENT_VERSION`, `_get_version` and `_SCHEMA_V1` leave `schema.py`, which stops being a second SSOT
- [x] [AC1] Update `src/garsync/db/__init__.py` exports, `cli.py:65`, `api/main.py:42`, `tests/conftest.py:16`, `tests/api/conftest.py:20`, and `tests/test_schema.py`
- [x] [AC1] Test: a v1 fixture built from `tests/fixtures/schema_v1.sql`, stamped `0001`, upgrades to head
- [x] [AC1] Test: a fresh database and a stamped-and-upgraded v1 database have equal `sqlite_master`
- [x] [AC1] Test: the drift assertion — `sqlite_master` compared against the expected schema, substituting for the `autogenerate` this project forgoes (R1)
- [x] [AC1] Test: `upgrade head` a second time is a no-op
- [x] Refactor pass over the new migration/config module for clarity

### 2 — The backup, before anything touches a file

- [x] [AC6] Failing test: the backup target produces a timestamped artifact that opens and reports the pre-migration row counts
- [x] [AC6] `make db-backup` → `VACUUM INTO 'data/backups/<db>-<UTC timestamp>.db'`, refusing to overwrite — **no preceding checkpoint**: `VACUUM INTO` already reads through the connection, so a checkpoint would only add a write to a database this code is only reading (R5)
- [x] [AC6] The upgrade path invoked by `make sync`/CLI calls the backup before the first revision
- [x] [AC6] `data/backups/` added to `.gitignore` (the artifact holds personal health data)

### 3 — The v2 revision, table by table

- [x] [AC2] Failing test: row counts survive, and all 9 `sync_log` rows appear in `ingest_run` with `source='legacy'` while remaining in the legacy table
- [x] [AC2] Revision `0002_v2`: create `ingest_run` (legacy columns + `source` + cursor columns nullable) and copy the legacy rows flagged `source='legacy'`
- [x] [P] [AC2] Rename `biometrics` → `daily_metrics` via `batch_alter_table`
- [x] [P] [AC2] Rename `sleep` → `sleep_sessions` and add `sleep_need_seconds` NULL — the design's shorthand gains its unit to match `total_sleep_seconds` beside it (ADR-009 §3)
- [x] [AC4] Failing test: `hrv_baseline_status` retains the legacy string verbatim and the numeric HRV columns are NULL on a row whose payload has no numbers
- [x] [AC4] `hrv_balance` → `hrv_baseline_status`; add the numeric HRV columns born NULL
- [x] [AC5] Failing test: `goals` exists, is keyed by `valid_from`, and no speculative table was created
- [x] [AC5] Add `goals` (goal weight, rate band, effective-from) and nothing else
- [x] [AC3] Failing test with hand-computed expectations: the `-420` and `-480` rows the real data contains, plus a synthetic DST-transition date (today's real range `2026-01-10 → 2026-03-01` contains no transition, so that case cannot come from the data)
- [x] [AC3] `activities`: add `source`, `source_id`, `tz_offset_minutes` and the derived Garmin columns; rebuild for `UNIQUE(source, source_id)` — **explicitly**, not through `batch_alter_table`: a batch add of a NOT NULL column needs a `server_default`, and `'garmin'` as a database default would silently label a future scale row (R6, revised in `verification.md`)
- [x] [AC3] Backfill `source='garmin'`; derive `tz_offset_minutes` per row from `startTimeGMT`, keeping the original local string in `raw_data`
- [x] [AC3] The missing-offset path: use `GARSYNC_TZ` **only** if explicitly set, otherwise abort naming the offending row ids — there is no default zone anywhere (R3: the real payloads are US Mountain/Pacific, so a European default would be ~8h wrong on this history and no fixture would catch it)
- [x] [AC4] Backfill the derived columns only where the payload carries them (`aerobic`/`anaerobicTrainingEffect` 100/100, `vO2MaxValue` 37/100, `activityTrainingLoad` 2/100) and expose the gap count as a queryable value (R7)
- [x] [AC1] `downgrade()` for the renames and additive columns, with a round-trip test on the fixture; the TZ transform is documented as forward-only in production per §4.1
- [x] [AC3] Post-upgrade assertions inside the revision: `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, row counts — failing the upgrade rather than warning
- [x] [AC6] **No `foreign_keys=OFF` pragma** — it would be ineffective inside the transaction *and* unnecessary: neither v1 nor v2 declares a foreign key. `test_v2_declares_no_foreign_keys` guards the assumption instead

### 4 — The readers move with the writers

- [x] [AC2] Failing test: `/api/sync/status` reports 9 legacy runs **by value** and the count **increments** after a pipeline run — this is the assertion that fails if the reader is left behind, which a shape-only test would not catch (R2)
- [x] [AC2] Rename `SyncLogRepository` → `IngestRunRepository`, moving **writer and reader together**: `log()`, `get_latest()`, `get_all()`, `count()`, with `sync_type` → `source` renamed inside the same methods
- [x] [AC2] Update `api/deps.py` wiring, `api/routes/sync.py`, and keep the response field names in `api/schemas.py` unchanged so the HTTP contract stays frozen
- [x] [AC2] Update `tests/api/conftest.py`'s sync-log seeding to target `ingest_run` with `source`
- [x] [AC2] Update `tests/test_repository_sync_log.py` (rename to `test_repository_ingest_run.py`) and `tests/api/test_sync_status.py`

### 5 — Rehearsal against the real database

- [x] [AC6] Integration-marked test (`-m integration`, skipped when `data/garsync.db` is absent): copy the file, back it up, upgrade the copy, assert row counts and the TZ transformation against the real rows
- [x] [AC6] Assert the source file is **untouched** — a digest before and after — because the rehearsal's whole point is that the original is never the subject
- [x] [AC4] Rehearsal reports the gap counts on real data (`training_load` 2/100) so the metric layer inherits the number rather than a surprise

### 6 — Closing the loop

- [x] [AC6] Update the `Key Paths` table in `AGENTS.md` (`schema.py` semantics, `migrations/`) and document the migration path wherever the runbook lives
- [x] [AC6] Raise `.coverage-baseline` to the value measured in the same commit as the tests that raised it
- [x] Documentation updated in the same PR (no doc debt: `docs/lessons/` entry is a promotion candidate at archive, not a promise)

## Closing

- [x] Every acceptance criterion from `proposal.md` is covered by at least one test
- [x] Every acceptance criterion has a matching entry in `features.json` with a non-vacuous verification command
- [x] Type checks pass
- [x] Lint passes
- [x] No unrelated changes in the diff (no scope creep)
- [x] `verification.md` filled in, including the measured evidence this proposal cites
- [x] PR opened referencing this spec folder

## Machine-readable features

This spec emits a sibling `features.json`, following [[pattern-feature-list-as-primitive]]. The JSON is the harness-facing contract: each acceptance criterion maps to ≥1 feature with `id`, `behavior`, `verification` (executable command), `state` (lifecycle), and `evidence` (harness-captured output).

**Pass-state gating:** the agent CANNOT write `"state": "passing"` — only the harness, after running `verification` and capturing exit code 0, may set that terminal state. Reviewers must reject PRs where `features.json` contains `passing` entries with empty `evidence`.
