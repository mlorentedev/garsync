---
id: "SUB-002"
type: spec
status: draft # draft | implementing | verifying | archived
created: "2026-09-24"
issue: "mlorentedev/garsync#83"   # repo#NNN — GitHub issue / Project item that tracks this spec
tags: [spec, proposal]
template_version: "1.0"
---

# SUB-002 — Ledger, atomic runs, idempotent writes

> **Ratified 2026-09-25.** D1–D4 and Q1–Q7 below are decisions of record, not proposals: the owner
> ruled on each, the alternatives are recorded with the evidence that would reopen them, and no
> section here is still waiting for an answer. Anything the ruling changed is marked *(ratified)*.

## Why

v1's ingestion has no run boundary — `SyncService.sync_range` (`src/garsync/pipeline.py:79-128`) writes
one row and one log entry per record, each committing on its own — so a crash or a rate limit leaves a
half-written day that looks like a successful partial sync, and nothing records *which window* was
covered or how far back a backfill may safely resume. Worse, the merged UPSERT is **destructive**: a
re-pull whose payload lacks a field writes `NULL` over a known value (measured, E2: `training_load
7.5 → NULL`, `normalized_power 231.0 → NULL`), and an identical re-pull changes `updated_at` (E1), so
ADR-008 §5's "zero new rows and zero changed values" is currently false on both counts. This PR gives
every adapter run one transaction, one ledger row and one coverage cursor, and makes re-ingestion a
provable no-op — the substrate the metric layer (SC-02: re-derive a trailing window), the Sync page
(SC-19) and the single ingest alarm (SC-10) all stand on.

## Rulings this spec implements (ratified — do not re-litigate without new evidence)

| # | Ruling | Where it lands |
|---|---|---|
| **D1** | **The cursor is a COVERAGE WATERMARK**, not "the timestamp of the last record seen" and not the run's wall clock: `cursor_after` = the end of the last successfully covered window, per `(source, sync_type)`, stored as an opaque monotone `TEXT` owned by the adapter. `window_end = truncate(now - settle(class), granularity(class))`; `window_start = min(previous successful cursor_after, local_today - trailing_days(class))`. Settle/granularity: activities 45 min / minute / ISO-8601 UTC; `daily_metrics` + sleep + stress local-day / `YYYY-MM-DD` in `GARSYNC_TZ`; weight uses the FitDays `sync_time` the cloud already provides (interface only — SCALE-001 owns the writer). **The cursor buys operator visibility and backfill resumption, never fetch savings** — the trailing window already re-derives morning revisions. | §What 2, 3 |
| **D2** | **Run grain = `(source, sync_type)`** = one transaction = one ledger row = one cursor. **Fetch happens outside the transaction, writes inside.** `BEGIN IMMEDIATE` on the writer (`isolation_level=None`), with the busy timeout made explicit. **Contradiction in ADR-008 §2/§3 resolved**: success rows commit *inside* the data transaction (invariant: a success row implies committed data); error rows are written *after* the rollback, in their own transaction, best-effort. | §What 1, 4; ADR-008 amendment |
| **D3** | **The asymmetry axis is RE-QUERYABILITY, not data class.** Garmin summary payloads stay where they are — in each row's existing `raw_data`, permanent — and are **never duplicated** into a `raw_payload` row (two stores = two retention windows = a replay whose result depends on which copy is read). Disk is not a constraint for summaries: measured 3586 B/activity · 16880 B/day · 701 B/night ⇒ ~8 MB/year against ADR-011 §9's 5 GiB. *(ratified)* `raw_payload` earns its place only for FitDays weight (SCALE-001) and `activity_streams` (SUB-004); the empty/no-row case (SC-02(3)) is answered **from the ledger**, so no payload store is created in this PR. | §What 5; ADR-008 amendment |
| **D4** | **Idempotency = the literal reading** (ADR-008 §5: zero new rows **and** zero changed values), via `ON CONFLICT(...) DO UPDATE SET … WHERE …` — valid in SQLite ≥ 3.24 and PostgreSQL. No per-row `SELECT`; no `CASE`; and **no** "compare payload columns except `updated_at`" allow-list, which would make §5 permanently false and hand-maintain a column list (lesson 026's shape-asserting-test trap). Carried-vs-absent: a `NULL` from the payload must not reach the DB as `NULL` over a known value. `rows_upserted` is redefined as **rows actually changed**; `rows_fetched` is added. | §What 6, 7 |

## What

Concrete behaviour after this PR:

1. **One run, one transaction, one ledger row.** `SyncService` runs one class at a time, keyed
   `(source, sync_type)`. Rows are fetched first (no transaction open, no lock held across HTTP), then
   every write for that run happens inside one `BEGIN IMMEDIATE` … `COMMIT`, together with the
   `ingest_run` success row. A failure rolls the whole run back and writes an `error` ledger row in its
   own transaction. `cursor_before`/`cursor_after` are recorded on both outcomes (unchanged on error),
   `started_at` is captured before the fetch, and `created_at` is the commit instant — the *finish*.
   Migration `0003` adds `rows_fetched` and `started_at` to `ingest_run` (additive columns, no rebuild).
2. **The window rule is one function, per class.** `window_end = truncate(now - settle(class),
   granularity(class))`, in the class's spelling (UTC minute for activities, `GARSYNC_TZ` local day for
   the daily classes). `window_start = min(last successful cursor_after, window_end -
   trailing_days(class))`, `trailing_days` default **14** (SC-02(1)). A gap longer than the trailing
   floor is closed in chunks: `window_end_effective = min(window_end, window_start +
   trailing_days)`, so no single run exceeds the 14-day span — i.e. ≈5 calls/day × 14 days + 1
   activity-list call ≈ **71 HTTP calls per daily run**, the number D1's arithmetic predicts and the
   rate-limit posture (ADR-008 §8) needs bounded.
3. **The cursor's only functional role is the left edge after a gap.** Inside the trailing floor it is
   always `window_end - 14 days`; only a gap longer than the floor moves it. That is what makes a
   resumable backfill (SC-08(4)) safe, and it is why a rest day (or a zero-row run) must still advance
   `cursor_after`: coverage is a property of the *window*, never of the records found in it.
4. **Atomicity is earned, not inherited** (SUB-001 decision 3, lesson 027): the writer takes its
   transaction from the driver (`isolation_level=None`) and issues `BEGIN IMMEDIATE` explicitly. The
   **trap this creates and the test that kills it**: with an explicit `BEGIN`, a repository's per-row
   `commit()` *ends the run's transaction* — measured this session, `in_transaction → False` and the row
   becomes visible to other connections — so "one transaction per run" is not achieved by adding a
   `BEGIN` alone. Repositories stop committing when a caller owns the transaction, and a test injects a
   failure mid-run and asserts every row of that run is gone.
5. ***(ratified)* No `raw_payload` in this PR — the ledger answers SC-02(3).** The two questions that
   distinction needs are answered by committed rows: *"did we ask, and was nothing there?"* is
   `status='success'` + the covered window in `cursor_before/after` + `rows_fetched=0`; *"is there no
   data for day D?"* is the absence of a row in the class's table for D. A payload store whose first
   writer records empty responses would append once per class per run — **~1.3k rows/day** — to
   duplicate what the ledger already commits, and its retention policy has no writer yet. `raw_payload`
   arrives with its first real writer (SUB-004 streams, SCALE-001 weight), carrying `retention_days`
   then; no speculative table is created now (the SUB-001 `test_no_deferred_table_was_created` posture,
   carried forward as `test_raw_payload_is_not_created_before_its_first_writer`).
6. **Re-ingestion is a no-op, in value and in text.** Every payload UPSERT gains a diff predicate
   (`… WHERE excluded.col IS NOT <table>.col OR …`, `IS NOT` so `NULL`s compare), so an identical
   re-pull executes no `UPDATE` at all: `changes() = 0`, `updated_at` does not move (measured E3/E5).
   `raw_data` is written as a **canonical re-serialisation** so the text cannot differ between two pulls
   of the same payload for reasons that carry no meaning (E6) — and the landing cost is declared, see
   "Declared cost" below.
7. **A known value is never erased by re-ingestion.** Absence must not reach the database as `NULL`:
   `col = COALESCE(excluded.col, table.col)` for the columns a request may legitimately not supply.
   ***(ratified, Q1)* The carried set is a per-table declaration**, not one shared activity constant:
   `client.py`'s `get_dict()` maps an empty endpoint response to `{}`, so a single empty endpoint among
   the four would otherwise null a day's RHR, Body Battery, stress or HRV on the *next* run of the
   14-day window. The invariant is stated, not implied: *erasing a known value requires an explicit
   action, never a re-pull.*
8. **The ledger answers "what changed", never `updated_at`.** `rows_upserted` counts rows whose values
   actually changed (`changes()`), `rows_fetched` counts what the adapter returned, and the cursor is
   read by ledger `id` — never by `created_at`, whose millisecond resolution can make two logical states
   share one value (E1 saw `NOTHING` until the pulls were separated). Nothing in this PR reads
   `updated_at` as a change signal.
9. **`/api/sync/status` keeps working, unchanged.** The new columns are additive and no route reads
   them yet; the Sync page (SC-19) owns that surface. The reader moves with the writer (lesson 026) —
   here the writer only gains columns, so the guard is that the existing route tests stay green.

### Declared cost (not a regression, and not measured away)

Canonicalising `raw_data` (item 6) rewrites the text of every already-stored payload once. The **first**
trailing-window pass after this lands will therefore report ~N rows changed in every class. The
idempotency assertion is run **twice**: the first pass may report the rewrite, the second must report
zero. A test asserts exactly that sequence, so the rewrite can neither hide a real change nor be
mistaken for one.

### Measured this session (2026-09-25, all on `/tmp` copies — the real DB is never opened for writing)

| Fact | Evidence |
|---|---|
| The E1–E6 findings reproduce unchanged | `/tmp/gs2/probe.py` re-run: E1 `changed=['updated_at']` · E2 `training_load 7.5 → None`, `normalized_power 231.0 → None` · E3 `changes()=0` · E4 the guard alone still writes NULL · E5 a real change lands · E6 same byte count, different text |
| `busy_timeout` is **not** absent | `PRAGMA busy_timeout` = **5000** with pysqlite's default `timeout=5.0`, with and without `isolation_level=None`. The brief's "no busy_timeout" is false as written; the ruling stands, the justification changes to *making a chosen 5 s explicit* |
| An explicit `BEGIN` is not enough for D2 | With `isolation_level=None` + `BEGIN IMMEDIATE`, a per-row `commit()` (today's `repo.upsert`) flips `in_transaction` to `False` and publishes the row to other connections — a silently broken run transaction |
| The v1 database holds February–March data | `daily_metrics` copy after migration: 4 rows, all carrying values, most recent **2026-03-01**; `data/garsync.db` mtime Mar 1 2026; no `garmin_tokens.json` on disk |

**M8/M9 are blocked, not answered.** Both need a live Garmin login, and every strategy is refused at
the network edge right now — **429 from Garmin's mobile endpoints and a Cloudflare 403 on the portal**,
on all four login strategies, with no cached token to fall back on. Each attempt extends the block, so
the response is to stop (ADR-008 §8's posture, confirmed by direct observation): **M8** (is the payload's
key order stable across two real fetches?) and **M9** (does any of the four endpoints return empty for a
day that already has values?) are filed for the next window, and this PR takes the declared defaults —
canonicalise `raw_data`, carried set per table. The block itself is evidence for the deployment work:
the credential path is the fragile one, and a token cache is the mitigation, not an optimisation.

### Prior art (researched 2026-09-25 — who already solved each of the four rulings)

Every *part* of D1–D4 is prior art; what this design adds is the composition. Nothing in the
surveyed space publishes an ingest ledger whose cursor is *coverage* rather than a record value, so
the three original bits are named at the end of the table.

| Ruling | Prior art | What it is called there | What we take — and where we differ |
|---|---|---|---|
| **D1** window + settle | `dlt` | **"lag / attribution window"**: *"you may want to always capture the last 7 days of data when fetching daily analytics reports … This is where the concept of 'lag' or 'attribution window' comes into play"*; `lag` is only valid with `last_value_func` of `min`/`max` | We take the moving window; we **differ** on the state: dlt's cursor is still the max/min **record value**, so a window that legitimately contains no rows never advances it — the exact defect D1 rules out |
| **D1** cursor semantics | **Airbyte** (`DatetimeBasedCursor`) | *"incremental syncs are usually implemented using a cursor value … records whose `updated_at` value is less than or equal [to] that cursor value have been synced already"*; *"Upon a successful sync, the final stream state will be the datetime of **the last record emitted**"*; `lookback_window: P31D` re-reads a month | Independent confirmation of the problem: a record-based cursor needs a defensive window bolted on, and Airbyte documents why — the *global substream cursor* **"enforces a minimal lookback window based on the previous sync's duration to avoid losing records added or updated during the sync"**. That hazard (rows landing *during* the fetch) is why our `window_end` is computed **before** the fetch and the cursor never moves past it |
| **D1** window, not clock | **Apache Airflow** (`data_interval`) | *"Each DAG run in Airflow has an assigned 'data interval' that represents the time range it operates in"*; *"A DAG run is usually scheduled after its associated data interval has ended, to ensure the run is able to collect all the data within the time period"*; *"you should always use `data_interval_start` or `data_interval_end` if possible, since those names are semantically more correct and less prone to misunderstandings"* (the older name was `execution_date`) | This is D1's ruling in another industry's words, **including the settle idea**: the run waits for the interval to end rather than running on wall clock. Our per-class settle/granularity table is that policy, specialised per data class |
| **D1/D3** re-pull is expected | **Garmin** (Health API, official) | *"end-users sync their device with Garmin Connect to upload device data, **at which point it is accessible via the API**"*; *"Developer Web Tools: … **backfill user data**"* | The vendor's own model is upload-gated availability + a supported backfill, i.e. coverage follows *upload*, and re-pulling a window is a designed operation, not an exception. *(The Wellness REST API Specification's `uploadStartTimeInSeconds`/`uploadEndTimeInSeconds` parameters are the stronger form of this, but every reachable mirror 403'd today — recorded as **CLAIMED**, not measured.)* |
| **D4** conditional UPSERT | **SQLite** `lang_upsert` + **PostgreSQL** `INSERT` | SQLite: *"The only use for the WHERE clause at the end of the DO UPDATE is to optionally change the DO UPDATE into a no-op depending on the original and/or new values"*, with the example `… WHERE excluded.validDate > phonebook2.validDate` — *"then the WHERE clause causes the DO UPDATE to become a no-op"*; *"UPSERT in SQLite follows the syntax established by PostgreSQL, with generalizations"*; added in **3.24.0 (2018-06-04)**. PostgreSQL's grammar shows the same optional `[ WHERE condition ]` | D4 is **documented prior art, not an invention** — and the docs name the mechanism *"a no-op"*, which is exactly ADR-008 §5's literal reading. Portability is asserted by SQLite's own docs; the version floor is 3.24, far below anything we run |
| **D4** merge intent | `dlt` (`write_disposition="merge"`), Airbyte (dedup on primary key) | Key-based merge with a primary key | Same intent; the difference is the *instrument*: our ledger counts rows that actually changed (`changes()`), which a framework merge cannot report cheaply |
| **Carried-vs-absent** | **RFC 7396** (JSON Merge Patch) | *"Null values in the merge patch are given special meaning to indicate the removal of existing values in the target"* | **A deliberate deviation, stated as one.** RFC 7396's null means *delete*; ours means *the request did not supply it*. We are not merging a patch of user intent — we are merging a vendor payload whose incompleteness is the very thing we are defending against — and the newest payload stays in `raw_data`, so a retained value is always auditable against the response that no longer carried it |

The three parts that are ours, and worth stating as such in review: **(1)** the cursor stores *coverage*, so a window with zero rows still advances it; **(2)** the settle/granularity policy is a per-class table rather than one global constant; **(3)** `rows_upserted` means *rows whose values changed*, which is the number an operator actually wants from a ledger.

### Executable-LOC budget

Estimated **~220 (ticket plan) / ~230 by construction** *(ratified: the `raw_payload` table and its
writer leave, which pays for the per-table carried set)*: migration `0003` (two additive columns) ~12 ·
`connection.py` transaction helper + explicit busy timeout ~35 · window module (class table + window
arithmetic) ~60 · `repository.py` guarded upserts + carried sets + ledger ~75 · `pipeline.py` per-class
run ~55. Tests, the ADR amendment and docs are excluded from the cap. **Named seam if it lands over:**
the window module's gap chunking is the only separable piece left, and the scheduler is already split
(Q3). An overage is declared in the PR body with these numbers.

## Out of scope

- **`raw_payload` (ratified deviation from `ticket-plan` §3).** Its retention policy is declared in the
  ADR amendment and implemented by its first writer — SUB-004 (streams) or SCALE-001 (weight). Nothing
  in this PR creates the table.
- **The scheduler** (in-process, APScheduler-style, off by default, one replica — ADR-008 §7). It is the
  most deferrable half of #83's scope and the first thing that would blow the LOC cap: **split** to its
  own spec/PR, which also owns `POST /api/sync/run` and the `GARSYNC_CRON` switch (Q3).
- **A windowed, paginated activities fetch.** Today activities are fetched by `limit` only
  (`pipeline.py:87`), so no honest coverage claim can be made for them; SUB-003 (`~160 LOC`) owns the
  date-range fetch and pagination. Consequence in §What is not applicable to activities, see Q4.
- **Retiring `sync_log`.** It stays in place and inert. The drop is a separate, irreversible
  forward-only revision; it needs its own ticket (Standing Order #4), not a silent ride here.
- **The Sync page (SC-19) and any new `/api` field.** The ledger's fields are additive and unread here.
- **Streams and stream-dependent metrics** (SUB-004), **FitDays/scale ingestion** (SCALE-001).
- **PostgreSQL-specific tuning.** Dev and tests are SQLite; the guarded UPSERT is chosen because both
  engines accept it, but nothing is measured on Postgres here.
- **#115 (which calendar day a row belongs to)** — explicitly deferred, boundary named in Q5.

## Ratified rulings on the open questions

Each was answered on 2026-09-25; the alternative and the evidence that would reopen it are kept.

- **Q1 — the carried set is per table.** *(ratified)* Not `DERIVED_COLUMNS` alone: `client.py`'s
  `get_dict()` turns an empty endpoint response into `{}`, so an empty `hrv`/`stress`/`heart_rates`
  response would null a day's known values on the next 14-day pass, exactly the E2 shape in two more
  tables. Each table declares the columns its request may legitimately not supply. *Reopened by:* a
  measured case where a value **must** return to `NULL` (Garmin retracting a metric), or a live run
  proving those four endpoints never come back empty for a day that already has a row — which is M9.
- **Q2 — no payload store for empty responses; the ledger answers it.** *(ratified)* Keyed
  `(source, source_key, fetched_at)` it appends once per class per run (~1.3k rows/day) to record that
  nothing arrived; the ledger's `status`/window/`rows_fetched` plus the absence of a class row carry the
  same information, committed. *Reopened by:* a named consumer that needs the payload *body* — a shape
  taxonomy where `200`+empty array, `200`+nulls and `404` yield different verdicts.
- **Q3 — the scheduler is split.** *(ratified)* Own spec + issue — proposed
  `SYNC-001-in-process-scheduler`: cron off by default, lifespan wiring, `POST /api/sync/run`,
  one-replica note. *Reopened by:* a decision to land #83 whole, which spends the LOC cap and mixes a
  scheduling concern into a substrate PR.
- **Q4 — the activities cursor stays `NULL` until SUB-003.** *(ratified)* The fetch is `limit`-based, so
  a cursor would claim a window the run never fetched. The activities run still writes its ledger row
  with `rows_fetched`/`rows_upserted`; a test asserts the `NULL`, refusing to claim coverage we did not
  take. *Reopened by:* a demonstration that the limit fetch can be made window-complete here for a few
  lines (date range + pagination is SUB-003's ~160 LOC).
- **Q5 — #115 is deferred, with the boundary drawn.** The cursor spells a day in `GARSYNC_TZ`, which is
  a *storage spelling for a coverage window*; row attribution (`date(start_time)` bucketing in
  `/api/activities` and `/api/stats/*`, and the derived daily layer) stays #115's. **The boundary: if
  any consumer ever derives an attribution from `cursor_after`, #115 resolves first.** No code in this
  PR buckets by the cursor.
- **Q6 — the daily class's right edge is *today*.** *(ratified)* "Settle at local midnight" reads two
  ways; *today* is the one that lets the 07:00 run (ADR-008 §6) ingest **last night's** sleep, which
  Garmin keys to the wake date — *yesterday* would delay every sleep row by a day and contradict SC-02's
  expected-by time. It is safe because the cursor never truncates the fetch below the 14-day floor: the
  cursor is a coverage claim, never a finality claim, and the end-of-day run refreshes the same day.
  *Reopened by:* a measured case where a `D`-keyed value written at 07:00 is wrong and is **not**
  corrected by the later run.
- **Q7 — SC-10's first clause is weaker than it reads.** *(ratified: recorded in the ADR amendment, the
  register text is left alone)* "a failed run, **or** no successful run within a threshold": the second
  clause derives from committed rows and always works; the first depends on a best-effort error-row
  write. The invariant is stated where it belongs — *a success row implies committed data, so the alarm
  keys on the **absence of success**, and the error row is diagnostic, never the signal.*
- **Carried, not fixed here:** `#119` (two Minor SUB-001 findings), `#116` (toolchain float), M4/M5/M6
  unrun, and **M7 (proposed)**: can an activity's stream still be re-fetched after 90 days? If not, the
  window is a data-loss boundary and ADR-008 §10's stream metrics can never exist for old activities —
  to be added to target-architecture §12's instrumentation list or filed.

## Acceptance criteria

- [ ] **AC1 — one run, one transaction, one ledger row.** A run whose write fails after its first upsert
      leaves **zero** data rows, zero `success` ledger rows, and exactly one `error` row (written after
      the rollback, in its own transaction). A successful run's `success` row is committed with its data.
- [ ] **AC2 — atomicity is not broken by the repositories.** With an explicit `BEGIN IMMEDIATE` open, a
      repository write cannot end the caller's transaction (`in_transaction` stays `True` across a
      batch), a mid-batch failure rolls back every row of that batch, and `upsert_batch` is atomic.
- [ ] **AC3 — the window rule is per class and bounded.** Table-driven: activities `window_end` is
      `now - 45 min` truncated to the minute in UTC `Z`; the daily classes' is the local `GARSYNC_TZ` day
      (today, Q6); the floor is 14 days; a gap of 30 days is closed in ≤14-day chunks with no run
      exceeding it; and the HTTP-call count for one full window matches the arithmetic (5/day × span + 1).
- [ ] **AC4 — the cursor is a coverage watermark.** A run that fetches **zero** rows still advances
      `cursor_after` to the window end; a failed run does not advance it; a cursor is never the run's wall
      clock (no `HH:MM:SS`-bearing value); a zero-row *daily* run advances it while the activities run's
      stays `NULL` (Q4); and the cursor is read by ledger `id`, never `created_at`.
- [ ] **AC5 — no lock is held across the fetch.** A client stub that blocks while being called observes
      `conn.in_transaction is False`, and a second writer can commit while it is blocked.
- [ ] **AC6 — idempotency is literal, proven on a narrower payload.** (i) A byte-identical re-pull
      changes nothing: zero changed rows and `updated_at` unmoved. (ii) A **strictly narrower** re-pull —
      a payload missing `activityTrainingLoad`/`normPower`/`avgPower`, an empty response in one of the
      four daily endpoints, and a day missing entirely — loses **no** known value and changes nothing.
      (iii) A real value change still lands.
- [ ] **AC7 — the ledger counts reality.** `rows_upserted` is the number of rows whose values changed
      (`changes()`-derived), `rows_fetched` the number the adapter returned; both are asserted from the
      ledger row for a run that mixed one changed row with several unchanged ones — with the
      canonical-serialisation pass run once before, and the zero-change assertion taken on the **second**
      pass (declared cost above).
- [ ] **AC8 — nothing reads `updated_at` as a change signal.** No production path added in this PR
      queries `updated_at` for incremental decisions (grep-level assertion over `src/`, plus the diff).
- [ ] **AC9 — SC-02(3) is answerable from committed data, and no payload store exists.** A covered window
      with `rows_fetched=0` and no class row answers "asked, nothing yet"; a covered window with rows and
      no row for day D answers "no data for D" — asserted as queries, and
      `test_raw_payload_is_not_created_before_its_first_writer` fails if the table appears early (the
      SUB-001 deferred-table posture).
- [ ] **AC10 — `/api/sync/status` and the four route suites are unchanged and green**, and `make check`
      passes with the coverage baseline not ratcheted down.
- [ ] **AC11 — the knowledge is recorded in this PR:** the ADR-008 amendment (D2's §2/§3 contradiction
      and its resolution; D3's companion-row deviation; Q7's invariant) exists in `docs/adr/`, and any
      lesson earned is in `docs/lessons/` **with** its `_index.md` row.
- [ ] **AC12 — the migration is additive and idempotent.** `0003` lands the same schema from a v1 fixture
      and from a v2 database, adds only `rows_fetched`/`started_at` (no table rebuild, no lying
      `server_default`), and re-running the chain changes nothing; the real `data/garsync.db` is still
      only ever migrated on a `tmp_path` copy.

## References

- Bitácora: [mlorentedev/garsync#83](https://github.com/mlorentedev/garsync/issues/83) (this spec) ·
  #114 (table ownership) · #115 (calendar day — Q5) · #116 · #119 · SUB-003 (windowed fetch) ·
  SCALE-001 (#97)
- ADRs: [`adr-008`](../../docs/adr/adr-008-ingestion-ledger-and-adapters.md) §2/§3/§4/§5/§6/§9/§10/§12/§13 —
  **amended by this PR** · `adr-009` (substrate, units at rest) · `adr-011` §9 (5 GiB ceiling)
- Design: `docs/architecture/target-architecture-v2.md` §4, §5 · `scope-interview.md` SC-02, SC-08,
  SC-10, SC-19 · `ticket-plan.md` §3 (SUB-002 ≈220 executable LOC; the `raw_payload` deviation is
  ratified above) · research/02 §4 (measured Garmin availability latency) · research/01 finding 17
  (`syncIncrements` takes its own `sync_time` cursor)
- Prior spec: [`specs/archive/SUB-001/verification.md`](../archive/SUB-001/verification.md) — the seven
  binding decisions (UTC at rest; `(source, source_id)` as natural key; cursors born NULL; atomicity
  *earned*)
- Prior art researched 2026-09-25 (passages quoted in §Prior art): [dlt — lag / attribution window](https://dlthub.com/docs/general-usage/incremental/lag) · [Airbyte — Incremental Sync / `DatetimeBasedCursor`, lookback windows](https://docs.airbyte.com/platform/connector-development/config-based/understanding-the-yaml-file/incremental-syncs) · [Airflow — DAG Runs / data interval](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html) and [FAQ](https://airflow.apache.org/docs/apache-airflow/stable/faq.html) · [SQLite `UPSERT`](https://sqlite.org/lang_upsert.html) · [PostgreSQL `INSERT` (`ON CONFLICT … DO UPDATE … WHERE`)](https://www.postgresql.org/docs/current/sql-insert.html) · [RFC 7396](https://datatracker.ietf.org/doc/html/rfc7396) · [Garmin Health API](https://developer.garmin.com/gc-developer-program/health-api/)
- Lessons: `lesson-026` (moving a writer without its reader) · `lesson-027` (SQLite commits DDL outside
  an explicit transaction)
