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

### Re-run for `0003` (2026-09-25, block 4)

The same rehearsal over the real database, this time measuring the chain rather than the write path:

- `0003_ledger_counts` is head on the copy; the original's SHA-256 (`6e116fd1…`) is unchanged, and a
  **second** `init_db` over the copy leaves its own digest unchanged — the chain is idempotent past the
  new revision.
- `PRAGMA table_info` on the migrated copy: `rows_fetched INTEGER NOT NULL DEFAULT '0'`,
  `started_at TEXT` with **`dflt_value` NULL** — the column the migration docstring refuses to default
  really has no default, so a `started_at` can only ever come from a run that captured it.
- Row counts survive verbatim (100 / 4 / 4 / 9 ledger rows), and the three `legacy` rows read
  `rows_fetched=0, started_at=NULL` — the honest encoding of "unmeasured", and the live evidence for
  decision 9 below: `rows_fetched=0` is *only* interpretable as AC9's "asked, nothing arrived" once the
  query excludes `source='legacy'`.

## Evidence per acceptance criterion

| AC | Evidence | State |
|---|---|---|
| **AC1** one run, one transaction, one ledger row | `tests/test_transaction.py` proves the boundary; the *run* that uses it is block 5 | **open** |
| **AC2** the repositories cannot end the caller's transaction | `TestTransactionOwnership` (3) + `TestBatchAtomicity` (3) + `tests/test_connection.py::test_the_driver_leaves_transactions_to_the_caller` | **done** |
| **AC3** the window rule, per class and bounded | `tests/test_window.py` (15 cases: the table, the half-open shape, gap chunking with no hole, the DST fold, the ≈71-call arithmetic, the zone that must be set) | **done** |
| **AC4** the cursor is a coverage watermark | the window carries `covered_through`; the ledger read/write is block 5 | **open** |
| **AC5** no lock across the fetch | the fetch/transaction split is block 5 | **open** |
| **AC6** idempotency, proven on a narrower payload | `TestNarrowerRepull` (6) + `TestNarrowerRepullDailyClasses` (3) + per-column omission tests over `DERIVED_COLUMNS`, `DAILY_METRICS_PAYLOAD_COLUMNS`, `SLEEP_PAYLOAD_COLUMNS` (17) + the rehearsal above | **done** |
| **AC7** the ledger counts reality | `upsert` returns the rows it changed (`rowcount`, measured equal to `changes()`); `TestLedgerCounts` (4) reads both counts back **from the ledger row** — one revised row among four re-fetched records `rows_upserted=1, rows_fetched=4`, the canonicalising first pass records 3 and the second 0, and `started_at` is NULL unless the run captured it. `sync_range` now passes the measured counts instead of `len(activities)` | **done** |
| **AC8** nothing reads `updated_at` as a change signal | the guard test is block 6 | **open** |
| **AC9** SC-02(3) from committed data, no payload store | block 6 | **open** |
| **AC10** routes and `make check` green | `make check` green at every commit; route suites unchanged | **done so far** |
| **AC11** knowledge recorded | ADR-008 amendment, lessons 028–031 + index, `target-architecture` §12 (M7, M8/M9 blocked) | **done** |
| **AC12** the migration is additive and idempotent | `0003_ledger_counts` adds the two columns and nothing else, no rebuild, no default on `started_at`; the chain test (same schema from a v1 fixture and from a v2 database, re-run changes nothing, real db reheard on a copy) is block 7 | **partial** |

## Test and gate status

- `make check` → lint ok · `mypy --strict` ok · **277 passed** · astro-check 0 errors · astro-build ok ·
  docs-build ok
- Coverage **85.88%** (1020 statements, 144 missed). `.coverage-baseline` reads 85.88 as of this commit:
  the number had been lagging the tree (85.67 since the idempotency suite, 85.17 recorded), because the
  tick that raises it lives in block 7 and was never read back — recorded in the file itself so the next
  reader does not repeat the pattern. `db/connection.py`, `db/repository.py`, `ingest/payload.py`,
  `ingest/window.py` all measure 100%.
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
8. **`started_at` gets no server default, and the pipeline captures it before the fetch.** `0003` could
   have used `CURRENT_TIMESTAMP` and every test here would still pass, but the default would stamp the
   ledger row's *insert* instant — the run's finish, which `created_at` already means — and the column
   would silently measure the write's own latency. NULL means "this run did not measure its start",
   which is true of every pre-SUB-002 row and of the `legacy` copies.
9. **`rows_fetched` is NOT NULL with a default of 0, which is also AC9's "asked, nothing arrived".**
   The collision is accepted rather than papered over: every writer from this commit on passes the
   count explicitly, so 0 means "nothing arrived" for anything this code writes, and the rows where 0
   means "unmeasured" are exactly the ones with `source='legacy'`, which are distinguishable by
   provenance. A nullable column would have made AC9's query a three-state test for no extra truth.
10. **`sync_range` was extracted into `_sync_activities` / `_sync_biometrics` / `_sync_sleep` + `_tally`.**
    Mechanically, not preemptively: writing the measured counts into the run made the orchestrator 66
    lines, over the repo's 40-line rule, and the seam the extraction names ("one run answers with what
    it fetched, or None") is the seam block 5 puts its transaction and cursor behind.

## Carried, and to be closed before the archive

- `AC1`, `AC4`, `AC5`: the cursor read/write and the per-class run — block 5, with the atomicity and
  no-lock-across-the-fetch tests written against a stub client.
- `AC12`'s chain test: block 7 (`tests/test_migrations.py` — same schema from a v1 fixture and from a v2
  database, only two columns added, re-running the chain changes nothing, the real db on a `tmp_path`
  copy).
- `AC8`, `AC9`: the guard over `updated_at` and the SC-02(3) queries — block 6.
- `M8`/`M9` remain **blocked** at Garmin's edge (429/Cloudflare), not answered; both took their declared
  defaults here.
