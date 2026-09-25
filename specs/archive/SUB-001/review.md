---
spec: "SUB-001"
verdict: "PASS"
reviewed_sha: "86828a473f15c64f09ef24f3d39b0d33b3b3d300"
reviewer: "nan/mimo-v2.5"
date: "2026-09-25"
---

## Adversarial review

**Scope**: SUB-001 — Schema evolution: Alembic, and the v1→v2 migration
**Sources**: `specs/SUB-001/{proposal,tasks,verification,features}.md`, `git diff d82c9719...HEAD` (2 commits: spec artifacts + timeutil offset-conversion fix + DST comment in `0002_v2.py`), full base commit `d82c9719` (the implementation), `tests/test_migrations.py` (46 tests), `tests/api/test_sync_status.py` (5 tests), `tests/test_timeutil.py` (26 tests), `src/garsync/db/migrations/versions/{0001_v1_baseline,0002_v2}.py`, `src/garsync/db/schema.py`, `src/garsync/timeutil.py`, `src/garsync/db/repository.py`, `src/garsync/api/schemas.py`.

### Spec and task alignment

Every AC maps to at least one named test class in `tests/test_migrations.py`:

| AC | Spec claim | Test class | Pass count | Verified |
|----|-----------|------------|------------|----------|
| AC1 | One schema creator, on the caller's connection | `TestAlembicSeam` | 10 | ✓ |
| AC2 | No row lost, readers moved with writers | `TestRowPreservation` + `test_sync_status.py` | 5 + 5 | ✓ |
| AC3 | UTC with per-row offset, no assumed zone | `TestTimezoneNormalisation` | 7 | ✓ |
| AC4 | Provenance and gaps explicit | `TestProvenanceAndGaps` | 7 | ✓ |
| AC5 | `goals` and nothing speculative | `TestGoalsAndNoSpeculativeTables` | 4 | ✓ |
| AC6 | HTTP contract frozen, gate green | `TestTheSnapshotBeforeTheMigration` + `TestRealDatabaseRehearsal` | 3 + 4 | ✓ |

The task list checkboxes all have matching diff evidence in the base commit. `features.json` lists 6 features, each with a non-vacuous verification command and `"state": "pending"` (correct — only the harness may set `"passing"`).

The diff from the base commit to HEAD contains spec artifacts, the `timeutil.py` offset-conversion fix (commit `86828a4`), and a DST comment in `0002_v2.py`. The implementation lives in the base commit and is reviewed as a whole change against the proposal.

### Findings

| Severity | Reality | Area | Finding | Evidence | Test (named, or UNTESTED) | Fix location |
|----------|---------|------|---------|----------|---------------------------|-------------|
| Minor | THEORETICAL | fallback-zone | `GARSYNC_TZ` validation is deferred to `_resolve_with_the_configured_zone` where `ZoneInfo()` raises `ZoneInfoNotFoundError`. This fires after `_copy_the_ledger()` has created `ingest_run`, but the entire upgrade is inside one transaction so the rollback is correct. The error message is less helpful than an upfront zone-name check. | `0002_v2.py:145` — `ZoneInfo(os.environ["GARSYNC_TZ"])` raises mid-upgrade | `TestTimezoneNormalisation::test_an_explicitly_configured_zone_resolves_the_straggler` (valid zone path only; invalid zone is UNTESTED) | code |
| Minor | THEORETICAL | downgrade-fidelity | `_as_v1_timestamp` always converts to UTC before formatting. A future v2 ingest run that stores a sleep timestamp with a non-UTC offset (not expected today — all v1 timestamps are `+00:00` — but architecturally possible if a future source writes one) would lose its offset in a downgrade. | `0002_v2.py:397` — `_as_v1_timestamp` always `.astimezone(UTC).isoformat()` | `TestTheDowngrade::test_it_reconstructs_the_local_start_time` (covers the current `+00:00` case only) | code (only if a future source writes non-UTC sleep timestamps) |
| Question | — | spec | AC2 says "all 9 `sync_log` rows exist in `ingest_run`" — correct for the real database (verified: 9 rows), but the migration test fixture (`seed_v1_rows`) only seeds 3. This is intentional per R4 ("scope the test to what the data can actually prove"), but a reader may expect the test to prove the claim at the stated number. | `tests/test_migrations.py:seed_v1_rows` inserts 3 rows; `data/garsync.db` has 9 | — | spec (documentation clarity only) |
| Question | — | spec | The spec's task list says "Update `AGENTS.md` (`schema.py` semantics, `migrations/`)" under task 6-AC6. The `AGENTS.md` change exists in the base commit but is not in the reviewed diff (`d82c9719...HEAD`), meaning it was in the base. This is correct per the launcher's base resolution, but a reader may wonder whether the Key Paths table was updated. | `AGENTS.md` is in the base commit's diff | — | — |

### Evaluator rubric

| Dimension | Grade | Rationale (one line) |
|-----------|-------|----------------------|
| Correctness        | A | All six ACs verified by named tests; edge cases (DST fold, missing payload, configured fallback, no-op re-upgrade) covered; no observed defects |
| Verification       | A | `make check` → 219 passed, 84.12% coverage; each AC maps to a named test class; real-database rehearsal with SHA-256 integrity assertion on the original file |
| Scope              | A | Diff matches proposal exactly; the two post-base commits (timeutil fix + DST comment) are within-scope fixes, not creep |
| Reliability        | B | Upgrade is atomic (explicit BEGIN); pre-flight refuses unreadable rows before any write; rollback is tested. Minor: `GARSYNC_TZ` invalid-zone error is deferred past the first write (safe due to single-transaction atomicity, but deferred validation is still deferred) |
| Maintainability    | A | All functions under 40 lines; clear naming; migration docstrings explain the *why* of each step; the frozen-DQL fixture (`schema_v1.sql`) decouples the test from the code it replaces |
| Handoff-readiness  | A | `verification.md` has measured evidence and seven documented implementation decisions; `features.json` is harness-ready; promotion candidates are listed with disposition |

### Verdict
PASS

### Recommended next steps

- **(Minor, code, optional)** Add an upfront `ZoneInfo` validation in `_refuse_unreadable_rows` or at the top of `upgrade()` when `GARSYNC_TZ` is set — fail fast with a clear message before any write, rather than deferring to `_resolve_with_the_configured_zone`. Not a blocker: the current single-transaction atomicity makes the deferred error safe.
- **(Minor, code, optional, deferred)** If a future source ever writes non-UTC sleep timestamps, `_as_v1_timestamp` in the downgrade path would silently shift them to UTC. Not actionable today; track as a latent concern.
- **`dotf spec archive` is advisable.** No Blockers, no REAL Majors; all rubric dimensions B or above; the contract set (`proposal.md`, `tasks.md`, `features.json`) is unchanged. The six features in `features.json` need their `state` set to `"passing"` by the harness after running the verification commands.
