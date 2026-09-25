---
tags: [spec, verification, ingestion, idempotency, sqlite, ledger]
created: "2026-09-25"
---

# Verification - SUB-002

> Evidence produced in this session, on branch `feat/ingest-ledger-idempotent-writes`.
> **Status: in progress** — the window rule, the transaction boundary and idempotency are implemented
> and verified below; the cursor/ledger wiring, the migration and the run itself are still open, and
> their rows say so.

## The rehearsal, on a copy of the only database

`/tmp/gs2/sub002probe.py` copies `data/garsync.db`, migrates the copy with the repo's own `init_db`, and
runs the *new* write path over the payloads the database already holds — 100 activities, 4 daily-metrics
rows, 4 sleep rows. The real database is never opened for writing (its SHA-256 is checked after the run
and is unchanged).

| Pass | activities | daily_metrics | sleep_sessions | Reading |
|---|---|---|---|---|
| **1** — canonical `raw_data` lands | **100 changed** | **4 changed** | **4 changed** | The declared landing cost, measured rather than estimated: every stored payload's text is rewritten once, in one real serialisation change |
| **2** — the same re-pull, now canonical | **0** | **0** | **0** | ADR-008 §5 holds: zero new rows **and** zero changed values |

And the defect this spec exists to close, on a real payload rather than a fixture:

```
--- E2: a re-pull from a payload that lacks the derived numbers ---
  rows changed = 0
  training_load 7.5 -> 7.5
  normalized_power 231.0 -> 231.0
  updated_at moved = False
```

Before this PR the same three lines read `7.5 -> None`, `231.0 -> None` (the measured live data loss).

## Evidence per acceptance criterion

| AC | Evidence | State |
|---|---|---|
| **AC1** one run, one transaction, one ledger row | `tests/test_transaction.py` proves the boundary; the *run* that uses it is block 5 | **open** |
| **AC2** the repositories cannot end the caller's transaction | `TestTransactionOwnership` (3) + `TestBatchAtomicity` (3) + `tests/test_connection.py::test_the_driver_leaves_transactions_to_the_caller` | **done** |
| **AC3** the window rule, per class and bounded | `tests/test_window.py` (15 cases: the table, the half-open shape, gap chunking with no hole, the DST fold, the ≈71-call arithmetic, the zone that must be set) | **done** |
| **AC4** the cursor is a coverage watermark | the window carries `covered_through`; the ledger read/write is block 5 | **open** |
| **AC5** no lock across the fetch | the fetch/transaction split is block 5 | **open** |
| **AC6** idempotency, proven on a narrower payload | `TestNarrowerRepull` (6) + `TestNarrowerRepullDailyClasses` (3) + per-column omission tests over `DERIVED_COLUMNS`, `DAILY_METRICS_PAYLOAD_COLUMNS`, `SLEEP_PAYLOAD_COLUMNS` (17) + the rehearsal above | **done** |
| **AC7** the ledger counts reality | `upsert` now returns the rows it changed (`rowcount`, measured equal to `changes()`); the ledger columns are block 4 | **partial** |
| **AC8** nothing reads `updated_at` as a change signal | the guard test is block 6 | **open** |
| **AC9** SC-02(3) from committed data, no payload store | block 6 | **open** |
| **AC10** routes and `make check` green | `make check` green at every commit; route suites unchanged | **done so far** |
| **AC11** knowledge recorded | ADR-008 amendment, lessons 028–031 + index, `target-architecture` §12 (M7, M8/M9 blocked) | **done** |
| **AC12** the migration is additive and idempotent | migration `0003` is block 4 | **open** |

## Test and gate status

- `make check` → lint ok · `mypy --strict` ok · **273 passed** · astro-check 0 errors · astro-build ok ·
  docs-build ok
- Coverage **85.67%** (1005 statements, 144 missed); `.coverage-baseline` raised 84.07 → 85.17 in the
  commit that paid for it (`ingest/window.py`), and `db/connection.py`, `db/repository.py`,
  `ingest/payload.py` all measure 100%.
- `scripts/check-lessons.sh` → OK (31 lessons).

## Decisions made during implementation

Each departs from the task list as written, and each has a reason that only became visible in the code.

1. **`resolve_window` returns a `Window`, not `Window | None`.** The draft's "nothing to cover" branch is
   **unreachable** while the trailing floor exists: `start <= end - trailing < end` always leaves at
   least one unit. The honest behaviour is the opposite of a no-op and is now asserted — a second run
   inside the same minute **re-derives the same window**, which is exactly how a morning revision lands.
   `trailing_days = 0` is a caller bug and raises.
2. **The window follows the ratified formula literally.** `start = min(cursor, floor)` re-covers the
   cursor's own unit rather than skipping it; the alternative (`cursor + 1 unit`) was a silent deviation
   from what was approved, and the test pins the difference.
3. **The repositories stopped committing altogether** rather than gaining a `commit: bool` flag. With
   `isolation_level=None` a statement outside a transaction has already committed, so the per-row
   `commit()` was doing nothing except being able to end a caller's transaction. `upsert_batch` opens a
   transaction of its own, and `transaction()` is re-entrant so a nested batch joins instead of
   committing — leaving no flag for a future caller to forget.
4. **`rowcount` is the change instrument**, measured equal to `changes()` for a guarded upsert (0 for a
   no-op, 1 for a real change, 1 for the insert), so the ledger does not need a second query per row.
5. **Three hand-written upsert statements became one generator.** The `SET` clause and the change
   predicate are produced from a single column list, because a hand-maintained predicate is exactly the
   column list that drifts (lesson 026) — and the carry rule has to appear in both halves of the
   statement. The generated SQL is still one grep-able constant per table.
6. **The carry set is per table, and the activities one is deliberately narrow.** The five derived
   columns (measured sparsity: `activityTrainingLoad` absent from 98 of 100 payloads) are carried; a core
   summary field like `calories` is not, so a `None` there still lands — and a test asserts that
   boundary, because the *set* is the decision, not "carry everything".
7. **`raw_data` is written by one function** (`ingest/payload.py::canonical_json`, sorted keys, compact
   separators) so the text can no longer differ between two spellings of the same payload — the first
   pass over the stored rows legitimately reports the rewrite, and the second reports zero.

## Carried, and to be closed before the archive

- `AC1`, `AC4`, `AC5`, `AC7`, `AC12`: the ledger columns, the cursor read/write and the per-class run —
  blocks 4 and 5, with the atomicity and no-lock-across-the-fetch tests written against a stub client.
- `AC8`, `AC9`: the guard over `updated_at` and the SC-02(3) queries — block 6.
- `M8`/`M9` remain **blocked** at Garmin's edge (429/Cloudflare), not answered; both took their declared
  defaults here.
