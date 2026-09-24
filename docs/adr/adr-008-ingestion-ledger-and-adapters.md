---
id: "adr-008-ingestion-ledger-and-adapters"
type: adr
status: accepted
owner: manu
date: "2026-09-24"
issue: ""
tags: [architecture, decision, ingestion, idempotency, scheduler, garsync]
created: "2026-09-24"
depends_on: [adr-007-purpose-built-single-user-platform]
---

# ADR-008: Ingestion via Source Adapters, an Append-Only Ledger and Idempotent Writes

## Status

Accepted — 2026-09-24. Replaces the `sync_log`-plus-implicit-retry model shipped in v1 and supersedes the ingestion half of `docs/architecture/prd-v1.md`.

## Date

2026-09-24

## Context

v1's ingestion was written for one source and one shape. Read from the repository on 2026-09-24, it has four properties that a multi-source, decision-feeding pipeline cannot have:

- `SyncService.sync_range` (`src/garsync/pipeline.py:79-128`) performs **one upsert and one log write per record, with no transaction**: a crash or a rate-limit mid-run leaves a half-written day that looks like a successful partial sync.
- **Activities are fetched by `limit`, never by date** (`pipeline.py:87`), so `--days` does not constrain them and history beyond `activities_limit` cannot be backfilled at all.
- There is **no scheduler**; ingestion happens only when a human runs the CLI, and the "latest synced date" watermark is derived from the `biometrics` table only.
- `sync_log` records a free-text status per entity type, which cannot answer "did the 07:00 run for the Garmin wellness pack complete, and how many rows did it change".

Three more sources are about to arrive (a scale, nutrition, and optionally an aggregator), each with a different cadence, a different failure mode and a different rate limit. The published cadence evidence also matters: Garmin publishes activities within ~10-30 minutes of device sync but sleep-derived metrics are **unstable for hours** and are revised later in the day, so polling harder buys wrong data rather than fresher data.

## Options Considered

1. **Keep the current shape, add more call sites.** Rejected: multiplies the non-atomicity and gives no run-level observability.
2. **A message broker (Redis Streams / NATS / Kafka) with consumers per source.** Rejected for now: it buys at-least-once delivery for a system with one consumer and one writer, at the price of a broker to run, back up and debug. The broker becomes justified when a second consumer or a push-only device appears (ADR-007 keeps that door open).
3. **Adapters + ledger + watermark + idempotent UPSERT in one process.** Chosen.
4. **A managed ETL/airflow-style scheduler.** Rejected as operational weight for one operator.

## Decision

1. **One adapter per source**, behind a common interface (fetch window → normalised rows + a cursor). `garmin`, `fitdays`, `scale_webhook`, `nutrition` are adapters; an `intervals_icu` adapter is added only as a secondary/validation path.
2. **One transaction per adapter run.** The `ingest_run` row and the data rows commit together. A failure rolls back and does **not** advance the cursor.
3. **`ingest_run` replaces `sync_log`**: source, cursor before/after, start and finish timestamps, status, rows upserted, error, and the counts per entity.
4. **`raw_payload` retains the upstream response** (JSON, retention-limited) so any window can be replayed after a schema or formula change. Discarding the vendor payload is what makes a formula change unrecoverable.
5. **Idempotency is a contract, proven by test**: a natural key per table, `ON CONFLICT ... DO UPDATE`, and a test asserting that re-running any adapter over an already-ingested window yields zero new rows and zero changed values.
6. **Cadence follows availability, not enthusiasm**: activities every 30 minutes during waking hours; the overnight wellness pack **once at 07:00 local**; stress and all-day aggregates once at end of day; scale on event with an hourly fallback; nutrition on write; the derived layer nightly and incrementally.
7. **Scheduler lives in-process** (APScheduler-style), off by default locally, enabled by configuration in a deployment. One replica, by construction — a second writer would race the PVC and the SQLite file, and the workload does not need one.
8. **Rate-limit posture is explicit**: token caching, a login-fallback chain, exponential backoff on 429, and a cadence that does not resemble scraping. The measured risk with the unofficial Garmin path is Cloudflare and rate limits, not account termination.
9. **`activity_streams` carries a retention window** (initial value: 90 days), while derived metrics persist indefinitely. Stated here so it is not discovered as a full disk.
10. **Stream-dependent metrics are computed at ingest time and persisted** (efficiency factor, decoupling, interval detection, duration curves). A formula change means recomputing from the retained `raw_payload`; a stream that was never retained cannot be recomputed at all — so the retention window is a *scope* decision about which historical metrics can ever exist, not a disk decision.
11. **Timezones are normalized at ingest, once.** Canonical timestamps are stored in **UTC**, the source's original local string is preserved inside `raw_data`, an explicit `tz_offset_minutes` column carries the offset, and every daily rollup is keyed to a configured `GARSYNC_TZ` **local calendar day**. This ends the current split in which activities are stored from a naive `startTimeLocal` while sleep is stored from a UTC epoch in the same database (`client.py:87` vs `client.py:108`) — a split that would silently shift every sleep-versus-training correlation the metric layer is built to compute.
12. **Backfill is a first-class, resumable operation (SC-08), with three different depths for three different costs.** *Summaries are fetched completely*: full Garmin activity history and daily wellness as far as the API paginates, plus the FitDays cloud's ~400 days. *Streams are not backfilled wholesale*: detail samples stay re-queryable from Garmin for old activities, so the design fetches them eagerly only for a recent window and **on demand** for any older activity that is opened — which turns the retention window of item 9 into a cache policy rather than a data-loss boundary, and keeps "maximum history" from costing gigabytes. *Raw-payload retention is asymmetric*, decided by the source's fragility: Garmin is re-queryable, so its payloads may be short-lived, while the FitDays cloud is a reverse-engineered surface that may vanish, so **its payloads are kept permanently** (one small row per weigh-in). Backfill runs as a one-off throttled command that never blocks a deployment, and the ledger cursor of items 3–5 is precisely what makes resumption safe.
13. **Re-derivation is not the same as re-ingestion (SC-02).** Because Garmin revises overnight metrics during the morning and a scale can upload hours late, each run re-derives a **trailing window** (14 days initially) rather than only the current day, and a measurement is attributed to the local day of **its own timestamp**, never to its arrival day.

## Consequences

### Positive

- Every ingest is observable and replayable; "did last night's data arrive" becomes a query, not a guess.
- A single, uniform idempotency rule makes retries, backfills and schema changes safe by construction.
- The 07:00/30-minute split removes the class of bug where a poller reads a value Garmin has not finished computing and stores it as final.

### Negative

- More moving parts than v1: a ledger, a payload store, cursors per source, and a test that must keep the idempotency contract honest.
- Retention on streams and raw payloads is a decision that now has to be maintained rather than ignored.

### Neutral

- The adapter interface is where the *next* source lands, which is the whole point: the scale pillar and the nutrition pillar plug in without touching the core.

## References

- `docs/architecture/research/02-garmin-ingestion-and-realtime.md`, `research/03-selfhosted-health-platforms.md`
- `docs/architecture/target-architecture-v2.md` §4, §5
- `docs/adr/adr-009-data-substrate-and-migrations.md`, `docs/adr/adr-012-scale-integration-route.md`
- Issues: SYNC-001 (#37) is subsumed by phases 0 and 2 of the target architecture
