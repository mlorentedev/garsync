---
tags: [spec, tasks, templates]
created: "2026-09-24"
---

# Tasks - SUB-002

> TDD order. One task = one focused commit. Tick as you go. Reorder freely while spec is in `draft` state; freeze once you start `implementing`.
>
> **Inline markers** (optional, additive — borrowed from `github/spec-kit`, adapt-not-adopt per #141):
> - `[P]` — this task has **no dependency on another unchecked task**, so it is safe to run in parallel (fan out to a `Workflow`, or just batch). TDD chains (test → implement → refactor of the *same* behavior) are sequential and must NOT carry `[P]`; independent behaviors can.
> - `[AC<n>]` — this task helps satisfy **acceptance criterion #`<n>`** from `proposal.md`. Lets `/spec check` map coverage deterministically; omit it and the check falls back to semantic judgment.

## Setup

- [x] `proposal.md` is complete and acceptance criteria are testable
- [x] No open questions left in `proposal.md` "Risks / open questions" (Q1–Q7 ratified 2026-09-25)
- [x] Branch created from `master`: `feat/ingest-ledger-idempotent-writes` (no phase/milestone in the name)
- [x] #83 self-assigned at pickup (flips the board to *In Progress*)

## Implementation

### 1. The window rule — pure, no database, no network

- [x] [P] [AC3] Failing table-driven test `tests/test_window.py::test_the_window_table`: activities `window_end` = `now − 45 min` truncated to the minute in UTC `Z`; daily classes = the local `GARSYNC_TZ` day, **today** (Q6); `trailing_days = 14`; a synthetic DST fold does not move the local day
- [x] [AC3] Implement `src/garsync/ingest/window.py`: the per-class `settle`/`granularity` table and `resolve_window(sync_type, now, last_cursor) -> Window`
- [x] [AC3] Failing test: a 30-day gap is closed in ≤14-day chunks (`end_effective = min(end, start + trailing_days)`), each chunk advancing the cursor, no day left uncovered
- [x] [AC3] Implement the chunking; assert the span invariant (no run exceeds a 14-day span)
- [x] [AC3] Failing test `::test_the_daily_window_costs_one_call_per_day_plus_the_list` — the ≈71-call arithmetic asserted over the window's unit count (the counting against a stub client lands with the pipeline in block 5, which is where the adapter exists)
- [x] Refactor for clarity (one class table; no branching per class outside it)

> **Found by the first cycle, and worth knowing:** the draft returned `Window | None`, with `None`
> meaning "nothing to cover". That branch is **unreachable** while the trailing floor exists — the floor
> always leaves at least one unit to re-cover — so the code now returns a `Window` unconditionally and
> the honest behaviour is asserted instead: a second run inside the same minute **re-derives the same
> window** (which is how a morning revision lands), and a trailing span of zero units is a caller bug
> that raises. The tests also pinned the ratified formula literally: `start = min(cursor, floor)`
> re-covers the cursor's own unit rather than skipping it.

### 2. One transaction, and the repositories cannot break it

- [x] [P] [AC2] Failing test `tests/test_transaction.py::TestTransactionOwnership`: with `BEGIN IMMEDIATE` open, a repository write leaves `in_transaction` `True`; a mid-batch failure rolls back **every** row; `upsert_batch` is atomic; and the measure that motivates it is pinned — a bare `commit()` inside the explicit transaction *does* end it (the negative control)
- [x] [AC2] Implement `transaction(conn)` in `src/garsync/db/connection.py` (`isolation_level=None`, `BEGIN IMMEDIATE`, commit/rollback on exit) and make the repository writes not commit under a caller-owned transaction
- [x] [AC2] Make the `busy_timeout` explicit in `get_connection` (it already measures 5000 via pysqlite's `timeout=5.0`), with the value and its reason in the docstring — `BUSY_TIMEOUT_MS`, pinned by `tests/test_connection.py::test_the_busy_timeout_is_stated_explicitly`

> **How the invariant is enforced, rather than remembered:** the repositories no longer commit at all.
> With `isolation_level=None` a statement outside an explicit `BEGIN` has already committed, so the
> per-row `commit()` was doing nothing except being able to end a caller's transaction; `upsert_batch`
> opens a transaction of its own, which a nested call joins instead of committing. `transaction()` is
> re-entrant for exactly that reason, and a nested failure propagates to whoever owns the unit of work
> instead of being swallowed by a partial commit. `db/backup.py`'s pre-`VACUUM INTO` commit stays as a
> guard for a connection built elsewhere, with the comment saying so.

### 3. Idempotency — literal, and proven on a narrower payload

- [ ] [P] [AC6] Failing test `tests/test_idempotency.py::TestNarrowerRepull`: (i) byte-identical re-pull → zero changed rows and `updated_at` unmoved; (ii) a **strictly narrower** payload (no `activityTrainingLoad`/`normPower`/`avgPower`) → no known value lost; (iii) a real value change still lands
- [ ] [AC6] Implement the guarded UPSERT (`DO UPDATE SET … WHERE excluded.col IS NOT activities.col OR …`) + canonical `raw_data` serialisation for `activities`
- [ ] [AC6] Failing test: the same three cases for `daily_metrics` (one of the four endpoints returning empty) and `sleep_sessions` — the **per-table** carried set (Q1)
- [ ] [AC6] Implement the per-table carried sets (`COALESCE(excluded.col, table.col)`) and their declaration, with the invariant in the docstring

### 4. The ledger counts reality

- [ ] [AC7] Failing test `tests/test_idempotency.py::TestLedgerCounts`: a run that mixes one changed row with several unchanged ones records `rows_upserted = 1`, `rows_fetched = N`, `started_at` set; the **first** pass over pre-existing rows may report changes (canonicalisation), the **second** reports zero
- [ ] [AC12] Implement migration `0003`: additive `rows_fetched INTEGER NOT NULL DEFAULT 0` and `started_at TEXT NULL` on `ingest_run` (no rebuild, no misleading default)
- [ ] [AC7] Implement the counts (`changes()` per row, summed) and the ledger write in `IngestRunRepository` (`log(...)` gains `rows_fetched`/`started_at`/cursor arguments, defaults preserving today's callers)

### 5. The run: fetch outside, write inside

- [ ] [AC5] Failing test `tests/test_sync_pipeline.py::TestNoLockAcrossTheFetch`: a client stub that blocks while being called observes `conn.in_transaction is False`, and a second writer commits while it is blocked
- [ ] [AC1] Failing test `::TestAtomicRun`: a write failing after the first upsert leaves zero data rows, zero `success` rows, exactly one `error` row written after the rollback; a successful run's `success` row commits with its data
- [ ] [AC1] [AC5] Implement the per-class run in `SyncService` (fetch → `with transaction(conn)` → upserts → `success` row; on failure → `error` row in its own transaction)
- [ ] [AC4] Failing test `tests/test_repository_ingest_run.py::TestCursors`: zero rows still advances `cursor_after`; a failed run does not; the value is never the run's wall clock; lookup is by ledger `id` (a row with a later `created_at` and a lower `id` loses); activities' cursor stays `NULL` (Q4)
- [ ] [AC4] Implement cursor read/write per `(source, sync_type)` with `status='success'` and `cursor_kind` handling for the activities exception

### 6. What the ledger answers, and what it must not

- [ ] [P] [AC9] Failing test `tests/test_ledger_coverage.py`: "asked, nothing yet" (covered window, `rows_fetched=0`, no class row) and "no data for D" (covered window with rows, no row for D) are both answerable from committed rows; `test_raw_payload_is_not_created_before_its_first_writer` asserts the table's absence
- [ ] [P] [AC8] Failing test `tests/test_updated_at_guard.py`: scan `src/**.py` and assert every `updated_at` occurrence is a write (SET clause) — no read decides anything
- [x] [AC11] Amend `docs/adr/adr-008-ingestion-ledger-and-adapters.md`: the §2/§3 contradiction and its resolution (success in-tx, error after rollback; the absence-of-success invariant for SC-10), D3's deviation from target-architecture §4's companion-row rule, and the retention policy that arrives with `raw_payload`'s first writer
- [x] [AC11] Add `M7` (can a 90-day-old stream still be re-fetched?) to target-architecture §12's instrumentation list, and note M8/M9 as blocked-at-the-edge with the measured 429/Cloudflare evidence
- [x] [AC11] Write the lesson(s) earned here into `docs/lessons/lesson-NNN-<slug>.md` **with** their `docs/lessons/_index.md` row (`scripts/check-lessons.sh` guards the pairing) — written as `027`–`031`: an explicit `BEGIN` is not a transaction boundary when the repositories commit underneath it, a pragma the driver already sets, retrying a rate-limited login, and a stored payload that is not a canonical change signal

### 7. Gate and closure

- [ ] [AC12] Extend `tests/test_migrations.py`: `0003` lands the same schema from a v1 fixture and from a v2 database; only the two columns are added; the chain is idempotent; the real database is still reheard on a `tmp_path` copy with its digest unchanged
- [ ] [AC10] `make check` green (ruff, `mypy --strict`, pytest, astro check/build, docs build); raise `.coverage-baseline` only if the new tests lift it, in the same commit that pays for it
- [ ] [AC10] Confirm `/api/sync/status` and the four route suites pass with their assertions unchanged
- [ ] Refactor pass: `SyncService` and `IngestRunRepository` under 40 lines/function, complexity < 10, nesting < 4

## Closing

- [ ] Every acceptance criterion from `proposal.md` is covered by at least one test
- [ ] Every acceptance criterion has a matching entry in `features.json` with a non-vacuous verification command
- [ ] Type checks pass
- [ ] Lint passes
- [ ] No unrelated changes in the diff (no scope creep) — in particular no `raw_payload`, no scheduler, no `sync_log` drop
- [ ] Declared in the PR body: executable-LOC breakdown, the `raw_payload` deviation from `ticket-plan` §3, and the canonical-serialisation landing cost
- [ ] PR opened with `Closes #83`, then every reviewer comment dispositioned in a `## Review triage` comment (`dotf pr triage-queue` exit 0 before claiming complete)
- [ ] `/adversarial-review SUB-002` proposed in the verification window (never self-served; not the implementing model)
- [ ] Filed separately, not ridden along: `SYNC-001-in-process-scheduler` (Q3), the `sync_log` retirement, and M8/M9 for the next network window

## Machine-readable features

This spec emits a sibling `features.json` (alongside this file) following [[pattern-feature-list-as-primitive]]. The JSON is the harness-facing contract: each acceptance criterion maps to ≥1 feature with `id`, `behavior`, `verification` (executable command), `state` (lifecycle), and `evidence` (harness-captured output).

**Pass-state gating:** the agent CANNOT write `"state": "passing"` — only the harness, after running `verification` and capturing exit code 0, may set that terminal state. Reviewers must reject PRs where features.json contains `passing` entries with empty `evidence`.

Every command below runs from the repository root and is expected to **fail** while the spec is `draft`.
