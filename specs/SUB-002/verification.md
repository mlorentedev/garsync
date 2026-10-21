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

### Re-checked at block 6 (2026-09-25)

The rehearsal costs seconds, and the claim it supports — "the chain lands on the real file, and the real
file is untouched" — is exactly the one a later revision could silently invalidate. Re-run: head is still
`0003_ledger_counts` on a fresh copy, the original's digest (`6e116fd1…`) is unchanged after **two**
`init_db` calls, and the rows are the same 100 / 4 / 4 / 9. Recorded because an unrepeated rehearsal is a
memory, not a check.

## Evidence per acceptance criterion

| AC | Evidence | State |
|---|---|---|
| **AC1** one run, one transaction, one ledger row | `TestAtomicRun` (3): a write refused on the second row leaves zero activities, one `error` row and no `success` row; the error row is read back from a **second connection** (it survived the rollback it records) while `in_transaction` is `False`; and at the instant each class's success row is written, a reader sees neither that row nor that class's data — probed **per class**, because the three runs commit separately. `test_partial_failure_continues` still proves the other half: one class failing does not stop the others | **done** |
| **AC2** the repositories cannot end the caller's transaction | `TestTransactionOwnership` (3) + `TestBatchAtomicity` (3) + `tests/test_connection.py::test_the_driver_leaves_transactions_to_the_caller` | **done** |
| **AC3** the window rule, per class and bounded | `tests/test_window.py` (26 cases: the table, the half-open shape, gap chunking with no hole **at four floor values**, the DST fold, the ≈71-call arithmetic, the zone that must be set, the one-unit stall) | **done** |
| **AC4** the cursor is a coverage watermark | `TestCursors` (6, repository level: an empty window still advances it, a failed run never does, an error row *carrying* a cursor is ignored, `id` decides over `created_at`, neither class nor source leaks, a legacy row is not a watermark) + `TestRunCursors` (5, run level: the pair is the covered window, a daily cursor is `YYYY-MM-DD` and never the clock, a chunked run advances exactly one new unit while `rows_upserted` reads 0, activities claim nothing (Q4), a rolled-back run leaves the watermark where it was) | **done** |
| **AC5** no lock across the fetch | `TestNoLockAcrossTheFetch` (2): the client stub observes `conn.in_transaction is False` on every call, and a second connection writes and **commits during the fetch** with `busy_timeout=0` — it would raise `database is locked` if `BEGIN IMMEDIATE` opened first | **done** |
| **AC6** idempotency, proven on a narrower payload | `TestNarrowerRepull` (6) + `TestNarrowerRepullDailyClasses` (3) + per-column omission tests over `DERIVED_COLUMNS`, `DAILY_METRICS_PAYLOAD_COLUMNS`, `SLEEP_PAYLOAD_COLUMNS` (17) + the rehearsal above | **done** |
| **AC7** the ledger counts reality | `upsert` returns the rows it changed (`rowcount`, measured equal to `changes()`); `TestLedgerCounts` (4) reads both counts back **from the ledger row** — one revised row among four re-fetched records `rows_upserted=1, rows_fetched=4`, the canonicalising first pass records 3 and the second 0, and `started_at` is NULL unless the run captured it. `sync_range` passes the measured counts for every class, and the error row carries what the run fetched | **done** |
| **AC8** nothing reads `updated_at` as a change signal | `tests/test_updated_at_guard.py` (19 cases): the tree scan — every occurrence in `src/` must be a write, with the occurrence count asserted non-zero so the guard cannot pass by absence — **plus the guard's own table**: 7 reads it must name (WHERE, ORDER BY, projection, `AND` predicate, `JOIN ON`, subscript load, name load) and 8 writes it must let through (`SET`, insert list, `SET … WHERE key`, dict key, store, `sa.Column` declaration, docstring, comment); a docstring-sharing-a-line case keeps the exemption syntactic; and a clause-level assertion that the guarded upsert decides on the key and never compares the column. Boundary stated in the file: this guards `updated_at`; the CLI's `MAX(date)` incremental decision is #123 | **done** |
| **AC9** SC-02(3) from committed data, no payload store | `tests/test_ledger_coverage.py` (12 cases) over `IngestRunRepository.covered_days` / `days_not_uploaded_yet` / `days_with_no_data`: SC-02(3)'s two answers held apart, and the third state (never asked) kept out of both; error rows and `source='legacy'` rows cannot cover a day; overlapping windows answered as the union of what was asked (the morning revision); the window clamped to the range asked; `raw_payload` asserted absent; four refusals, one of them a drift guard asserting `DAY_KEYED_TABLES` cannot silently diverge from `CLASSES` | **done** |
| **AC10** routes and `make check` green | `make check` green at every commit; `tests/api/` unchanged and passing — the reads keep working because no column name moved and `DailyMetrics.total_weight_kg` is a view, not a rename | **done so far** |
| **AC11** knowledge recorded | ADR-008 amendment, lessons 028–031 + index, `target-architecture` §12 (M7, M8/M9 blocked) | **done** |
| **AC12** the migration is additive and idempotent | `0003_ledger_counts` adds the two columns and nothing else, no rebuild, no default on `started_at`; the chain test (same schema from a v1 fixture and from a v2 database, re-run changes nothing, real db reheard on a copy) is block 7 | **partial** |

## Test and gate status
### The contract, run verbatim (block 5)

The twelve `features.json` commands were executed as written, from the repository root, and the selected
case count recorded next to each exit code (lesson 034 — an exit code without a scope is not evidence):

| Feature | Command result | Cases selected |
|---|---|---|
| f1 `TestAtomicRun` | exit 0 | 3 |
| f2 `test_transaction.py` | exit 0 | 6 |
| f3 `test_window.py` | exit 0 | 22 |
| f4 `TestCursors` | exit 0 | 6 |
| f5 `TestNoLockAcrossTheFetch` | exit 0 | 2 |
| f6 `TestNarrowerRepull` | exit 0 | 9 |
| f7 `TestLedgerCounts` | exit 0 | 4 |
| f8 `tests/test_updated_at_guard.py` | exit 0 (block 6) | 19, and 15 of those are the guard's own table |
| f9 `tests/test_ledger_coverage.py` | exit 0 (block 6) | 12 |
| f10 `make check` | exit 0 | the whole gate |
| f11 ADR-008 + `check-lessons` | exit 0 | 33 lessons, index paired |
| f12 the `0003` chain | exit 0 | **1, and the wrong one** |

f12 is the finding: its filter `'Revision0003 or upgrading_twice'` matches a single pre-0003 test, and
`grep -n "0003\|rows_fetched\|started_at" tests/test_migrations.py` returns nothing. It was set back to
`pending` for that reason — AC12 currently rests on the hand-run rehearsal above, which documents a fact
and guards nothing. Block 7 writes the real one (`0003` adds exactly two columns and no table; a fresh v2
database and one migrated from a v1 fixture are schema-identical; re-running changes nothing) and widens
the command to match.


- `make check` → lint ok · `mypy --strict` ok · **332 passed** (`not e2e`) · astro-check 0 errors ·
  astro-build ok · docs-build ok
- Coverage **87.43%** (1074 statements, 135 missed). `.coverage-baseline` reads 87.43 as of this commit:
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
11. **A gap-closing chunk needs at least two units (`MIN_CHUNK_UNITS`).** `end_effective = start +
    trailing_days` re-covers the cursor's own unit — the re-cover is how a morning revision lands — so at
    `trailing_days = 1` the chunk covers a day it already had, `covered_through` reads the cursor
    unchanged, and the run repeats forever looking successful while the gap never closes. Found by
    driving the window from a run, not from the window's own suite, whose convergence loop ran only at
    the value the floor could then take (lesson 033). The clamp is `max(trailing_days, 2)` in
    `_chunk_units()`, one function both granularities call; at the ratified 14 it is inactive, so the
    ≈71-calls arithmetic is untouched.
12. **The ledger's `sync_type` vocabulary follows `CLASSES`** (`daily_metrics`, `sleep`, `stress`,
    `activities`), so `sync_type` and the table written agree by construction and the coverage query
    (AC9) needs no per-source mapping. v1 rows say `biometrics` and nothing maps them: no reader
    consumes the value today — `/sync/status` takes the daily timestamp from `daily_metrics` itself and
    the day report from `activities.start_time` — and `target-architecture` §2.5 defers the `legacy`
    mapping decision to the same ticket, which is the audit's moment, not a mapping added now.
13. **`cursor_before`/`cursor_after` are the covered window** (proposal item 5), not
    "previous watermark, new watermark". A run whose chunk covers three days reads
    `(2026-03-01, 2026-03-03)`; the previous watermark is the prior row's `cursor_after` in the same
    `(source, sync_type)`, so nothing is lost by the reading. A test written against the other reading
    failed first, and the test was wrong.
14. **`--days N` sets the floor, not the coverage list** (D1). The per-day ledger rows the CLI used to
    write are gone with it: `dates` maps to `trailing_days = max(len(dates), 1)` and `now` defaults to
    `datetime.now(UTC)`, injectable for tests. Two consequences were handled rather than absorbed.
    (a) The ledger's grain is now one row per class per run, and **no document had to change to say so** —
    see the correction below: I first wrote that §2.4's "one `ingest_run` row per day per sync_type" was
    superseded "in a doc edit, made here", and that sentence does not exist in `target-architecture-v2.md`,
    on this branch or on `master`. The design's `ingest_run` row names columns and is **silent about grain**,
    and the per-day rows were a property of `SyncService`'s loop, not of the doc. (b) The mapping is not the bound it looks like,
    and the CLI has a branch that skips the run entirely: `cli.py:21` takes `today` in **UTC** while the
    daily keys are `GARSYNC_TZ`-local, so between local 00:00 and 00:59 the newest key reads as tomorrow,
    `_dates_to_sync` returns `[]`, the CLI prints "Everything is up to date" and **no ledger row is
    written** — a run that does not ask cannot claim coverage (AC4) and cannot be distinguished from a
    scheduler that never fired. Measured on the live function, `--days 7`: newest key 60 days old → **8**
    dates (the list is inclusive at both ends, so the flag under-bounds by a day exactly when the caller
    most wants a bound); `today` → 1 date; `today + 1` → 0. Filed as **SYNC-002 #123** with the
    reproduction and three options, not fixed in scope: user-visible behaviour, and `make sync DAYS=…`
    semantics belong to their own review. Recorded here because the description I first gave — "the
    short-circuit fires when the tables reach today" — was **wrong**; the corrected one is in #123 and in
    an erratum comment on #83, since the owner's PR-shape decision was being made on the strength of what
    this branch says it left behind.

**A third self-correction, in the same register as the size figure and lesson 034.** This sitting produced
two claims that reached durable artifacts without being checked against the thing they cited: the size
(461, measured over whole files instead of added lines) and the §2.4 quotation above, which was
**invented** — a sentence I believed the design held, quoted it, and then reported it superseded by an edit
that had not been made. The failure is not the misreading; it is that both times the citation *felt*
recalled rather than read. The rule that came out of it: `grep` before quoting a document, and when a claim
says "changed here", name the commit in the same breath — an unhashable claim is a plan, not a record. No
doc edit is needed for this change: §3's "ONE TRANSACTION per run" already said the thing the code now does,
and `git show 431fc9d -- docs/architecture/target-architecture-v2.md` is the whole of what was touched in
that file on this branch (the M7/M8/M9 block).
15. **`GARSYNC_TZ` is now needed by every run**, because a daily class resolves at rest too — the window
    is derived, not asked for. `docker-compose.yml` passes it through as `${GARSYNC_TZ:?...}` so compose
    **fails closed** at boot instead of starting a service that raises on its first sync, and the test
    suite sets it explicitly (it is a host env var that leaks into tests, and a test that inherits it is
    not measuring the same thing twice).
16. **SC-02(3)'s two answers are separate queries, and a third state belongs to neither.**
    `days_not_uploaded_yet` is a day inside a covered window whose every covering run fetched zero rows;
    `days_with_no_data` is a day inside a covered window that did return rows, absent from the class table;
    a day outside every window was **never asked** and appears in neither list — which is the property the
    staleness alert depends on, since SC-02(3) tunes the threshold above normal lateness and a coverage
    hole is not lateness. `covered_days` is the only function permitted to answer with an empty set,
    because "no window covers this range" *is* the third state (lesson 035).
17. **Coverage questions are refused rather than answered empty.** `activities` (minute-resolved, no
    cursor until SUB-003), `stress` (windowed, no storage yet) and an unknown class name all raise; and
    `DAY_KEYED_TABLES` is asserted against `CLASSES` instead of trusted, so a newly declared day class
    cannot quietly become queryable. The alternative — returning `[]` — reads downstream as "we looked and
    there was nothing": a claim about the body, manufactured by a fact about the code.
18. **`rows_fetched` separates the two answers; `rows_upserted` could not.** Had AC7's honest count not
    landed first, both queries would have had to infer "was there anything" from the class table, which
    collapses "asked, nothing arrived" into "no data for D" — they are the same shape when nothing arrived
    anywhere. That is why block 4 preceded block 6 instead of being merged into it.

## Carried, and to be closed before the archive

- `AC12`'s chain test: block 7 (`tests/test_migrations.py` — same schema from a v1 fixture and from a v2
  database, only two columns added, re-running the chain changes nothing, the real db on a `tmp_path`
  copy).
- Nothing is carried for AC8/AC9: block 6 settled both. AC9's *consumers* (the day report, the
  staleness alert threshold) are other tickets — the ledger now answers the question, which is what this
  issue owned.
- `M8`/`M9` remain **blocked** at Garmin's edge (429/Cloudflare), not answered; both took their declared
  defaults here.

## The diff's size, measured (for the PR body's declaration)

**Method** (three steps, reproducible; the number is a decision input, so it is not left to a proxy):

1. `git diff --unified=0 master...<tip> -- <path>` → the added line numbers on the tip side of each hunk.
2. `ast.walk` over `git show <tip>:<file>` → the linenos of every `stmt` (minus `def`/`class` headers) and
   every `expr` — declarations, table rows and comment blocks excluded, continuation lines included once.
3. Intersect. A line the branch did not add is not this diff's size; a line that is only prose is not
   executable.

| Range | src/ executable lines added | Largest contributors |
|---|---|---|
| `master…7ef61e0` (blocks 1–3: transaction, window, idempotency) | **235** | `ingest/window.py` 99, `db/repository.py` 94, `db/connection.py` 20 |
| `7ef61e0…811efd3` (blocks 4–5: ledger counts, the per-class run) | **171** | `pipeline.py` 113, `db/repository.py` 24, `window.py` 17, `0003_ledger_counts.py` 17 |
| block 6 (SC-02(3) coverage queries) | **64** | `db/repository.py` alone: three queries, two helpers, one map |
| `master…working tree` (the whole branch so far) | **465** | 235 + 171 + 64; the ranges above sum to 470 because block 5 rewrote 5 lines block 3 had added |
| `tests/` over the branch (excluded from the cap) | 1136 | `test_sync_pipeline.py` 293, `test_idempotency.py` 204, `test_window.py` 198, plus block 6's two files at 154 and 159 |
| `docs/` + `specs/` (excluded) | 967 insertions | this file, ADR-008, lessons 028–034 |

The repo's cap is ~300 executable lines per PR (ADR-017). **Both halves are under it** — and block 6 kept
them level: splitting at the existing seam now yields 235 and 235, with the last commit's 64 lines landing
where the AC12 chain test will also land (block 7 is expected to stay small).

```
corrections, recorded rather than swallowed. Two earlier numbers in this file were wrong, and the
second one changed advice I had already given.

  - "~317 executable src lines" came from a line-based proxy (blanks, `#` comments and docstring
    delimiters stripped). It counted docstring bodies and missed continuation lines.
  - "461 for blocks 1–4" came from counting the AST statements of every file the branch creates or
    touches — read volume, not added lines. `repository.py` has 146 statements and the branch added 94
    of them; the old measure booked the whole file.
  - Consequence, and this is the part that matters: the 461 figure is what produced the statement
    "the branch is over the cap either way, because blocks 1–3 are ~311". That is false at the honest
    measure — blocks 1–3 are 235. A split at the existing seam puts both PRs inside the cap, so the
    overage declaration the owner was being asked to approve is not forced after all. The option that
    remains genuinely open is one PR of 401 with the seam declared (the substrate reviewed next to the
    code that finally uses its counts) versus two PRs of 235 and 171.
  - The seam that is still rejected is 1–2 / 3–4: it would ship one or more releases in which
    `rows_upserted` holds the fetched count — the number this spec exists to stop writing.
```
