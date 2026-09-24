---
id: "garsync-target-architecture-v2"
type: architecture
status: proposed
created: "2026-09-24"
owner: manu
tags: [garsync, v2, architecture, fitness, health, planning]
supersedes_nothing: true
evidence_base: "docs/architecture/research/01..07"
---

# GarSync v2 — Target Architecture

> **Pass 1 of N.** This is a design proposal produced in an architecture session on 2026-09-24, from
> seven commissioned research briefs (`docs/architecture/research/`). It is written to be attacked:
> every decision below is either **decided** (with an ADR), **recommended** (awaiting the owner's
> call), or **conditional** (blocked on a measurement we have not taken yet). Nothing here is
> implemented.

---

## 0. How to read this document

| Marker | Meaning |
|---|---|
| **[D]** | An ADR records this decision — in pass 1 every such ADR is `status: proposed`, so read [D] as "decided by this pass, pending the owner's confirmation" |
| **[R]** | Recommended — evidence points one way, owner has not confirmed |
| **[?]** | Conditional — blocked on a measurement (see §12 Instrumentation first) |
| **[X]** | Explicitly rejected — do not re-litigate without new evidence |

The evidence base is seven briefs in `docs/architecture/research/`, each written with
MEASURED / CLAIMED / INFERRED markers against primary sources on 2026-09-23/24. Where this document
asserts a fact about the outside world, the brief is the citation of record. Nothing here is asserted
from memory.

**Pass 2 — adversarial review, done.** An independent model (`nan/mimo-v2.5`, not the model that
wrote this) attacked this document and the ADRs; the review and the adjudication of every finding are
recorded in [`review-v2-pass1.md`](review-v2-pass1.md). One Blocker was acknowledged and fixed here
(§4.1), one was downgraded after reading the licence text (§8), and one was rejected with reasons.

**Pass 3 — scope locked with the owner.** Every open decision was answered one question at a time and is
recorded in [`scope-interview.md`](scope-interview.md) (SC-01 … SC-14); §1.1 lists what it changed.
ADR-007 … ADR-013 are `accepted` as of 2026-09-24, carrying the conditions each names (ADR-011 on M6,
ADR-012 on M4).

---

## 1. What v2 is

**One sentence.** GarSync stops being a Garmin dashboard and becomes a single-user personal health
platform that ingests training, recovery, body composition and nutrition, computes one auditable
metric layer over all four, and delivers a daily briefing and a weekly adjustment — with every number
traceable to a formula and a source row.

**Four pillars**, in the order their data becomes available:

| Pillar | Source | State today |
|---|---|---|
| **Training** | Garmin Connect (`garminconnect`) | Ingested as summaries; streams and derived metrics missing |
| **Recovery** | Garmin overnight (HRV, RHR, Body Battery, readiness, sleep) | Partially ingested; HRV stored as a *string*, no numeric series |
| **Body composition** | FitDays-only scale | **Nothing ingested.** No table exists |
| **Nutrition** | Manual / Open Food Facts | **Nothing ingested.** No table exists — and it is out of v2 scope (SC-01) |

### 1.1 Scope locked (pass 3)

The authoritative scope is the register in [`scope-interview.md`](scope-interview.md) — SC-01 … SC-14, all
answered with the owner on 2026-09-24, one question at a time. The product this document now describes:

> **A private, single-user application that ingests Garmin training and a FitDays smart scale, and shows
> how the body responds to the training — every number traceable to a formula and a source row, and a
> weekly review instead of a dashboard to remember to open.**

Six things the interview changed, each of which had been load-bearing here:

| Change | Cause |
|---|---|
| **Nutrition leaves the MVP** — no tables, no loop, no ODbL question on the critical path | SC-01, SC-03 |
| **BLE capture leaves the MVP** — the FitDays cloud becomes primary, conditional on one 5-minute test | SC-09 (test M4) |
| **Recovery is conditional, not a pillar** — the owner rarely sleeps with the watch, so sleep, HRV, RHR, Body Battery and Training Readiness are absent most days | SC-05 |
| **The hero is the load↔body-response relationship**, not a morning readiness score | SC-06 |
| **No LLM anywhere in v2** — the weekly review is deterministic; this supersedes the live ADR-005 | SC-11 |
| **Delivery is a weekly review plus one alarm about system health** — never about behaviour | SC-07, SC-10 |

**Scope verdict [D — ADR-007].** There is no open-source backbone that covers these four for one
athlete, and the projects that came closest either stopped at one vertical or died of general-health
platform weight. GarSync stays **purpose-built and single-user**, and copies proven mechanics
(idempotent ingestion, a unit contract, a metric registry, real migrations) rather than adopting a
platform.

**Non-goals for v2** (each is a different product, not a later task): multi-user tenancy, FHIR/openEHR
interoperability, a native mobile app, social features, clinical claims, an injury-risk model, a
general-purpose coaching engine that serves people other than the owner.

---

## 2. Current state — verified, not remembered

Facts established by reading the repository in this session, not from the vault's `context.md`:

| Fact | Evidence |
|---|---|
| 11 open issues; 3 open PRs; **#66 and #70 have a failing `frontend` check** | `gh issue list`, `gh pr view` |
| All three open PRs are **effectively unreviewed**: CodeRabbit posts `Review skipped — bot user detected`, and `pr-agent.yml` documents that `NAN_API_KEY` is not set here | PR comments, workflow header |
| `dotf pr triage-queue` exits 0 — which means *no pending dispositions*, not "reviewed" | command output |
| `specs/SEC-001` was merged in #44 and its issue is closed, but the spec is **unarchived**, its last task box is unchecked, and there is **no `review.md`** | `specs/SEC-001/`, `git log` |
| `schema_version` exists, but there is **no migration mechanism** — only `_SCHEMA_V1`, `CURRENT_VERSION = 1` | `src/garsync/db/schema.py` |
| `sync_range` writes per record with **no transaction**; a crash mid-sync leaves partial data | `src/garsync/pipeline.py:79-128` |
| Activities are fetched with a **limit, never a date filter**, so `--days` does not constrain them and no backfill exists beyond 100 records | `pipeline.py:87` |
| **Two timezone semantics in one database**: activities carry naive local `startTimeLocal`, sleep carries UTC from a GMT epoch | `client.py` |
| `pandas`, `streamlit`, `plotly` are declared dependencies with **zero references** in `src/` or `tests/` | `grep`, `pyproject.toml` |
| `docs/lessons.md` (8 entries) and `docs/lessons/` (21 files) are **duplicate SSOTs** since the split in #58 | both paths |
| `GEMINI.md` is stale (references `make test-backend`, which does not exist) and there is **no canonical `AGENTS.md`** | `GEMINI.md`, `Makefile` |
| The README advertises MIT and links `LICENSE`; **the file does not exist** | `git ls-files LICENSE` → empty |
| CI has no `permissions:`, no `concurrency:`, runs `pytest` without coverage (though `pytest-cov` is installed), and has no frontend tests or lint | `.github/workflows/ci.yml`, `pyproject.toml` |

These are recorded as findings, not as tickets — the ticket plan is its own step (§13, step 0).

---

## 3. Target topology

```
                    ┌──────────────────────── one container, one replica ────────────────────────┐
 Garmin Connect ───▶│  INGEST WORKER  (APScheduler, in-process, off by default locally)           │
 FitDays cloud  ───▶│    adapters/  garmin │ fitdays │ nutrition │ scale_webhook                 │
 BLE capture    ───▶│        ↓ normalize → metric registry (canonical units)                      │
 (separate proc)    │        ↓ ledger: ingest_run + raw_payload, ONE TRANSACTION per run         │
 Nutrition UI   ───▶│        ↓ idempotent UPSERT on natural keys                                  │
                    │                                                                              │
                    │  DERIVED LAYER  deterministic, pure functions, unit-tested, replayable        │
                    │        ↓                                                                     │
                    │  FastAPI  /api/*  ·  /healthz  ·  /metrics                                   │
                    └───────────────┬──────────────────────────────┬───────────────────────────────┘
                                    │                              │
                    PostgreSQL (prod, kubelab)          Apprise ──▶ Telegram
                    SQLite WAL (dev + tests)            07:00 brief · Sunday weekly review
                                    │
                    Astro PWA (Today / Trends / Body / Log)   ·   read-only agent token (MCP, later)
```

**Why a single container [D — ADR-008].** The scale-capture half fails differently from the API and
carries a licence boundary, so it is a *separate process* (§7); everything else stays in one process
with one writer, which keeps SQLite honest in dev and keeps the deployment one manifest in prod.

---

## 4. Data model v2

The idempotency contract, applied uniformly: **a natural key, an UPSERT, and a source column**.
Re-pulling any window must be a no-op. Every table that receives external data also has a companion
row in `raw_payload`.

| Table | Key | Notes |
|---|---|---|
| `activities` | `activity_id` + `UNIQUE(source, source_id)` | add derived columns from Garmin payloads: `training_load`, `aerobic_te`, `anaerobic_te`, `normalized_power`, `avg_power` |
| `activity_streams` | `(activity_id, ts)` | per-second detail — HR, pace, power, cadence, altitude. **Retention window, not forever** (§5) |
| `daily_metrics` | `date` | one row per day: RHR, HRV **numeric** (`last_night_avg`, `weekly_avg`, baseline low/high), Body Battery high/low, stress avg, steps, training readiness **plus its factors**, training status, VO2max |
| `sleep_sessions` | `date` | stages, score, plus `sleep_need` so sleep debt has a stated denominator |
| `weight_measurements` | `UNIQUE(source, measured_at)` | **raw only**: `weight_kg`, `impedance_ohm`, `source`. Never derived values |
| `body_composition` | `(measurement_id, algorithm)` | one row **per algorithm** (`vendor`, `blescalesync`, `deurenberg`, …). Two algorithms disagree by ~10 points of body fat on the same reading; they are never merged into one field |
| `nutrition_entries` | `UNIQUE(source, source_id)` | day, meal, grams, kcal, protein/carb/fat, food reference |
| `targets` | `(valid_from)` | the loop's own state: kcal and protein targets, plus the evidence that produced them |
| `derived_daily` | `date` | CTL, ATL, TSB, ramp rate, monotony, strain, HRV z, RHR deviation, sleep debt, SRI, readiness **and its named contributors**, `data_quality` |
| `metric_registry` | `code` | `system` (`garsync`/`garmin`/`loinc`), canonical `unit` (UCUM), `dtype`, `agg`, `polarity`. FHIR-shaped, no FHIR server |
| `ingest_run` | `id` | `source`, cursor before/after, timings, status, `rows_upserted`, error |
| `raw_payload` | `(source, source_key, fetched_at)` | replayability after a schema or formula change; retention-limited |
| `recommendation_log` | `id` | every recommendation, its inputs, and the later outcome. Without this, "confidence" is unfalsifiable |
| `auth_audit` | `id` | login success/failure, session create/destroy, token issue/revoke |

**Dropped:** `sync_log` is replaced by `ingest_run` (same idea, richer and per-source).

**Units [D — ADR-009].** Canonical SI-ish at rest (kg, metres, seconds, bpm, ms, °C), display units
only at the edge, conversion is the *receiver's* job. The contract lives in a document and a test,
copied in spirit from the one open-source project that solved it publicly.

---

### 4.1 Migration of the existing database [D — ADR-009]

The v1→v2 migration is specified here because an underspecified migration over years of history is the
single highest-risk item in this plan, and because a real database already exists on disk
(`data/garsync.db`). One Alembic revision set, forward-only in production, with a test that upgrades a
v1 fixture and asserts row counts **and** the timezone transformation.

| Existing | Becomes | Transformation |
|---|---|---|
| `activities` | `activities` + `source`, `tz_offset_minutes`, the Garmin derived columns | `source = 'garmin'` backfilled; derived columns re-read from `raw_data` with **no refetch**; `start_time` normalised to UTC using the stored offset if present, otherwise `GARSYNC_TZ` evaluated at the original date; the original `startTimeLocal` string kept inside `raw_data` |
| `biometrics` | `daily_metrics` + a numeric HRV series | `hrv_balance` retained as `hrv_baseline_status`; numeric HRV columns left NULL and backfilled by re-ingesting raw payloads where retention allows, otherwise accepted and reported as gaps rather than invented |
| `sleep` | `sleep_sessions` (+ `sleep_need`) | direct copy; `start`/`end` normalised to UTC; `sleep_need` stays NULL — with the watch off at night (SC-05) nothing in v2 consumes it |
| `sync_log` | `ingest_run` | copied with `source = 'legacy'` and flagged as cursor-less; the old table is kept read-only for one release, then dropped |
| `schema_version` | Alembic's `alembic_version` | the baseline revision **stamps** the existing database rather than recreating it |

Rules: a backup is taken before the migration runs, the migration is exercised against a copy before
the only copy, and every backfilled column either has a source or is explicitly reported as a gap.

## 5. Ingestion architecture

Cadence follows **data availability, not polling enthusiasm** — the briefs measured when Garmin
actually publishes each class:

| Class | Cadence | Latency floor | Why |
|---|---|---|---|
| Activities | every 30 min during waking hours | ~10–30 min after device sync | publish shortly after sync |
| Sleep, HRV, RHR, readiness, Body Battery | **once daily, 07:00 local** | overnight processing | values are *unstable* for hours and change later in the day. **Conditional on wearing the watch overnight (SC-05): on days without it, these are expected to be absent, not late** |
| Stress, all-day aggregates | once, end of day | same day | no value in polling |
| Weight / body composition | **cloud poll twice daily** (morning + evening), BLE only if M4 fails | minutes to hours (cloud) | the failure mode is a silent never-uploaded weigh-in, and **M4 is the measurement that decides it** |
| Derived layer | nightly + incrementally on new data | — | deterministic |

Nutrition has no row in this table: it is out of v2 scope (SC-01).

**Hard rules [D — ADR-008]:**

1. **One transaction per source run.** Ledger row and data rows commit together; a failure leaves no
   half-written day and does not advance the cursor.
2. **Idempotency is proven by test**, not asserted: re-running any adapter over an already-ingested
   window must produce zero new rows and zero changed values.
3. **Rate-limit posture, not ban posture.** The measured risk with `garminconnect` is Cloudflare and
   429s, not account bans. Token caching, a login fallback chain, exponential backoff, and a cadence
   that does not look like a scraper.
4. **No new third-party dependence without a named failure mode.** `intervals.icu` is available as an
   optional secondary/validation path (free tier, documented API, webhooks) — never as the only source.
5. **Stream-dependent metrics are computed at ingest time and persisted**, because `activity_streams`
   itself has a retention window (initial value: 90 days). A formula change means recomputing from the
   retained `raw_payload`; a stream that was never retained is not recoverable at all — so the window
   is a *scope* choice about which historical metrics can ever be recomputed, not merely a disk choice.

**Garmin is not a bus [R].** Using Garmin as the transport for scale data is tempting (zero new code
paths) and it makes an external vendor the system of record for a body-composition series we intend
to reason over. Recommendation: ingest the scale **directly**, and optionally *mirror* to Garmin for
portability, never the reverse.

---

## 6. The metric layer — what we compute and what we refuse to

**Stance [D — ADR-013].** Deterministic, auditable, reproducible. Almost nothing here needs a model,
and the published evidence says the model-shaped parts (ACWR-as-a-decision, injury risk scores) are
exactly the ones that fail external validation.

**v1 computes** (all pure functions over data the ingester already holds): HR-based load (`hrTSS` from
zone time; Garmin's `activityTrainingLoad` shown alongside as a cross-check), CTL/ATL/TSB with
λ = 2/(N+1) and 42/7 windows, ramp rate as 7-day Δ as % of CTL, monotony and strain, RHR 7-day mean
and deviation, HRV as ln-rMSSD trend + weekly CV + personal baseline z, sleep debt against a stated
need, sleep regularity index, and perceived-vs-actual once a plan exists.

**v1 refuses:**

| Refused | Reason |
|---|---|
| ACWR as a decision input | reported descriptively at most; the literature does not support gating advice on it |
| Injury-risk scores | 30/30 externally-unvalidated base rate |
| Any trained model | nothing here needs one, and none could be validated on one person |
| DFA α1 thresholds, orthostatic tests | require protocol control and hardware the owner does not have |
| A 0–100 black-box readiness score | the score may be shown for familiarity, but the **contributors must be visible** |

**Readiness [R]** is a transparent z-score sum over 3–5 named inputs, each displayed with its own
delta against a personal baseline, plus a per-day `data_quality` flag ("12 of 14 days present").
Whether to mirror Garmin's Training Readiness or replace it turned out to be **moot** (SC-05/SC-06):
Garmin's readiness is absent on most days because the watch stays off at night, so the app does not
compete with it — the recovery panel appears when data exists, and the MVP's centre of gravity is the
load↔body-response relationship instead.

**Recommendations [D — ADR-013]** are capped, logged in `recommendation_log`, expressed as ranges,
and gated on concurrence: the system may downgrade or remove a session only under named conditions,
and it must be able to say "insufficient data, changing nothing". A system that only describes is safe
and useless; a system that speaks without a stated confidence is worse than useless.

---

## 7. The scale pillar

**Route decision [D, pass 3 — SC-09].** The route is **cloud-first**: the FitDays cloud poller is the
primary source and BLE capture leaves the MVP. This inverts pass 1's ranking, and the reason is
simplification rather than preference — the cloud poller is required *anyway* as the only source of the
~400 days of history (SC-08), and the owner reports that the scale already syncs and uploads through the
app. Making it primary removes a process, all hardware, a GPL boundary and about a week of work.

It is **conditional on one 5-minute test (M4)**: weigh in with the phone in another room, then check
whether the app shows the reading **with its original timestamp**. That test exists because "it already
syncs" describes what happens when the phone is present, and the failure mode otherwise is silent — a
weigh-in that never uploads is indistinguishable from not weighing. Pass 1's BLE analysis is kept below,
because that is what the remedy looks like if M4 fails.

**The premise in the request is not quite right, and that matters.** "FitDays" is an *app*
(Guangdong ICOMON), not a scale family; it fronts at least three physically different BLE families,
and two of them will hand their measurement to whoever is listening. So the constraint is a property
of the vendor's cloud, not of the hardware.

**Step 0 is a measurement, not a decision [? M4].** If the weigh-in test shows that a reading taken with
no phone present is lost, a BLE scan (advertised name, service
UUIDs, manufacturer ID + raw bytes) collapses the whole decision tree:

| Identified as | Route | Qualities |
|---|---|---|
| `AAA002/007/013`, or manufacturer-id `0xC0` with a valid checksum | passive advertisement decoding | no phone, no vendor, real-time on stabilisation |
| `SWAN` / `icomon` / `YG` / service `0xFFB0` | active GATT daemon (connect-and-hold) | best local payload — composite frames carry fat/muscle/bone/water |
| `ADV` / `Chipsea-BLE` / `Yoda*`, manufacturer `0x20CA` | passive **with impedance** | best passive case |
| none of the above | cloud polling or replace the scale | see below |

**Ranked routes — as a *remedy* ranking, ordered for the case where M4 fails [R].** For the MVP the cloud
is primary (see the route decision above); this list is what to reach for if the weigh-in test shows that
readings taken without the phone are lost.

1. **BLE capture as a separate process, not a library inside `src/garsync/` [D — ADR-012].** The
   mature BLE scale daemon is **GPL-3.0**; running it as its own container and consuming its MQTT or
   webhook output keeps the copyleft at a process boundary, keeps the capture host free to sit next to
   the scale, and lands on kubelab's existing broker. Owning the ~1 week of `bleak` + `FFB0` code is
   the alternative if we want no third-party dependency at all.
2. **Cloud polling** — promoted to primary for the MVP by SC-09. Listed here because its properties are
   exactly what make it viable as the only path *and* what M4 measures.
   and one is a clean async Python client; it yields the richest payload and ~400 days of history
   immediately. It is also a private, rotating, single-maintainer surface: use it to *backfill and
   reconcile*, never as the only path.
3. **Replacement scale** — the honest escape hatch if the identification lands on an unsupported
   family, and the cheapest route to a well-supported protocol.
4. **App-mediated CSV export** — the forever-manual fallback, kept as a documented emergency only.

**Reconciliation is explicit [D — ADR-012].** Local BIA and vendor numbers are different models and
will not agree (a measured case: 39.7% vs 29.1% body fat from the same reading). One source is
declared the **system of record** for the series; every other algorithm's output is stored in its own
`algorithm`-tagged row. Nothing is averaged.

**Presentation [D].** Weight and its EMA trend are point values. Body fat, fat mass, lean mass,
visceral fat, "metabolic age" and scale-derived BMR are **trends with bands**, behind a one-line
caveat, defaulting to the 7-day median — because a consumer BIA scale misses DEXA fat mass by a median
of 2.2–4.4 kg and a lab-grade multi-frequency device still carries a systematic offset.

---

## 8. The nutrition pillar and the closed loop — **deferred out of v2 (SC-01)**

> Kept in the document as the design of the *deferred* feature, because the decisions below are already
> reasoned and would otherwise be re-derived. **None of this is in the MVP**: no tables, no UI, no ODbL
> question on the critical path. Reopening it is its own decision, not a phase of this plan.

**Scope is settled: nutrition is deferred out of v2 (SC-01).** The three viable paths below remain
reasoned here for the day it reopens, because they differ by an
order of magnitude in build cost:

| Option | Cost | Notes |
|---|---|---|
| Manual quick-entry of repeated meals + a thin private UI over Open Food Facts bulk data | Low | OFF/USDA for lookups, attribution in the UI, no API keys, no vendor |
| Integrate an existing open nutrition tracker as a separate container | Medium | licence obligations if code is copied — run it as a process, never vendor the source |
| Build a full food logger with barcode scanning | High | rejected for v2 |

**Data licence [D — ADR-007].** The Open Food Facts database is ODbL, its contents DbCL, its images
CC-BY-SA. ODbL §4.5(c) exempts internal, non-public use from share-alike, so the private instance is
unencumbered — and keeps attribution in the UI as a matter of good faith. But §4.4(c) makes a
Derivative Database "Publicly Used" as soon as a *Produced Work* derived from it is published, so the
OFF-backed cache is **private-only and never feeds the public demo**, which therefore carries no
nutrition-derived aggregate at all (§9).

**The loop [R]**, weekly and capped:

1. Require **≥5 logged days in the last 7**. Otherwise publish "insufficient data" and change nothing.
2. Compute a robust 28-day weight slope against logged intake; derive adaptive expenditure as
   `mean intake − slope × 7716 kcal/kg`.
3. Adjust the calorie target by **no more than 150 kcal per week**; hold macros unless the protein
   target itself moved.
4. Write the new target into `targets` **with the evidence that produced it**, so "why did my target
   change" is answerable from the database.

Protein is expressed as a range (higher per kg of fat-free mass in a deficit), energy availability is
a soft screening flag at most, and the RED-S flag is either omitted in v1 or explicitly labelled as
weak — the fat-free-mass denominator is the least trustworthy number in the system.

---

## 9. Access, privacy and sharing

**Two independent boundaries [D — ADR-010]**, because one of them exists precisely for the day the
other is misconfigured:

1. **At the edge:** Authelia forward-auth on the public hostname at the infrastructure's second
   factor (kubelab only — see §10). A Committed break-glass IngressRoute restricted to the VPN, plus
   `kubectl port-forward`, both surviving GitOps reconciliation.
2. **In the application:** server-set session cookie (`__Host-`, `Secure`, `HttpOnly`, `SameSite=Lax`),
   passkey-first with TOTP as the recovery path, Argon2id for any password, server-side session store
   with idle + absolute timeouts and **real revocation** (this is SEC-002, promoted from a nice-to-have
   to a prerequisite), session-ID regeneration on login, and 401-not-302 for XHR so the PWA can prompt.

**Sharing in v1 is an export, not a route.** A recurring "show my doctor" need is served by an
age-encrypted PDF/CSV generated on demand, which costs a fraction of the risk of an unauthenticated
endpoint over Article 9 data. No public route exists in v1, so no share-authorization bug can exist.

**One scoped agent token [D]**, hashed at rest, revocable, logged, read-only, for LLM tooling.

**Multi-user is a different product, not a later feature [X].** It forces a tenant boundary into every
query (SQLite has no row-level security), an identity product (registration, recovery, lockout, an
account-takeover path ending in someone else's medical data), and GDPR controllership for other
people's special-category data. The trigger that would justify it: *a second person's own data must
live in the system* — not "someone wants to see mine".

**A public portfolio surface is a separate deployment [R].** Derived aggregates only (volume, streaks,
counts), from a separate database, with no weight, body-composition, sleep, HRV or resting-HR series —
and said out loud, in the README, as permanent and correlatable — and with **no nutrition-derived
aggregate**, for the ODbL reason in §8. That is the honest version of "or even anyone".

---

## 10. Deployment

**Recommendation [R — ADR-011]: private instance in kubelab prod (Hetzner K3s), portfolio demo
optionally on NaN Basic Space.** The two are different products with different data and different gates.

| Dimension | kubelab prod | NaN Basic Space |
|---|---|---|
| Auth | Authelia forward-auth **plus** app session | app session only (no platform auth exists) |
| Reachability | public hostname + VPN-only break-glass | public hostname, always |
| Data | shared PostgreSQL, existing backups | SQLite on a PVC; **no documented PVC backup** |
| Secrets | SOPS + age, existing path | dashboard env vars only, no masking |
| Observability | Loki + Vector + Grafana, alerting exists | live logs in a dashboard |
| Notifications | Apprise service already deployed | none |
| Promotion | Argo CD + immutable tags | auto-build on push |
| Fit | **the private instance** | **the seeded public demo** |

Concrete kubelab work items this implies (each a cross-repo dependency, not something GarSync's repo
can decide alone):

- a service manifest under `infra/k8s/base/services/` plus the prod overlay, with
  `secure-headers`, `rate-limit`, `crowdsec-bouncer` and `authelia` middlewares;
- secrets under the `apps.services.<category>.garsync.*` namespace, SOPS-managed;
- Postgres database + role, and **a decision on migration ownership** — the platform's shared Postgres
  mandates a specific migration tool for *its own* schema, which is not automatically the app's
  business. This needs to be settled with kubelab before the first migration ships;
- PVC backup coverage for whatever state stays local, and a restore drill;
- `toolkit deployment promote --app` currently accepts only `api|web|errors`: promoting a third
  product needs either a generalisation of that allow-list or a per-product Argo CD Application. This
  is a platform gap to raise, not a GarSync patch;
- a resource footprint that fits the VPS envelope: request 128MiB RAM / 0.1 CPU, limit 256MiB / 0.5
  CPU, and disk bounded by ADR-008's retention caps (90-day streams plus retained raw payloads) to
  ≤5GiB. The summary and derived tables are megabytes, not gigabytes, at two years of history.

**Observability minimum [D]:** `/healthz` exposing database reachability and
`last_sync_age_seconds`, one alert at >36h of staleness, and structured logs already flowing to Loki.
This single item is what stops the product becoming a stale-data museum.

---

## 11. UX and DX surface

**Information architecture [R]:** `Today` is the product — one headline number, its named
contributors with baseline deltas, one sentence of what changed, and a coverage line. `Trends`,
`Body`, `Log` are siblings behind a bottom tab bar. Today's single page of KPI cards, heatmap and one
trend chart is a *report of numbers*; the differentiator is compression and honesty.

**Delivery beats dashboards [D — SC-07]:** a **Sunday weekly review** through kubelab's existing
Apprise → Telegram — the load↔body-response relationship, the week's sessions, **one** adjustment
sentence and the coverage line. There is no daily brief: with a hero that moves on a weekly timescale
and no plan in the system, a daily message would be short or empty most days and would train the owner
to ignore the channel. Push is reserved for exactly **one** class, and it is about the system, not about
the owner: **the ingest is broken** (SC-10). The PWA stays as a wrapper on the dashboard rather than
becoming a phase of its own.

### 11.1 The weekly review, specified

The weekly review is the product's only scheduled delivery, so its content is not left to taste.

| Slot | Content | When the data is absent |
|---|---|---|
| Hero | the **load↔body-response relationship** for the week: where the weight and body-fat trend sits against the goal band, and what accumulated load did over the same 28 days | `insufficient data — 2 weigh-ins in 14 days` |
| Contributors | up to three named inputs with their own deltas, e.g. `carga +12% WoW` · `peso −0,4 kg / 28 d` · `masa magra −0,2 kg` | omit the slot; never invent a contributor |
| Sessions | one line: how many, how long, how much load — and the ramp against the previous week | `no sessions logged` |
| Coverage | `7 of 7 weigh-ins · 5 sessions · last ingest 3 h ago` | always shown |
| Adjustment | **one** sentence, rule-driven and traceable, e.g. `load +12% with lean mass falling → slow the ramp` | `no change: insufficient data` |
| Link | one deep link to `Body` or `Trends` | always shown |

**Honesty cues are a feature, not a disclaimer [D]:** publish the formula and the coverage next to
every derived number, show personal baselines rather than population ones, and separate the
directly-measured half of the dashboard from the modelled half visually.

**DX gaps to close [D — table below]**, all measured against the engineer's own more mature repos
(kubelab/dotfiles) and the research brief's benchmark of comparable projects:

| # | Gap | Fix | Priority |
|---|---|---|---|
| 1 | `README` badges MIT, **no LICENSE file** | add MIT `LICENSE` | v2-0 |
| 2 | No canonical `AGENTS.md`; `GEMINI.md` is stale and duplicated | one `AGENTS.md`, retire the drift | v2-0 |
| 3 | No `pre-commit`, no gitleaks | adopt the sibling repos' pre-commit set | v2-0 |
| 4 | CI has no `permissions:`/`concurrency:`; no coverage gate | tighten, and **measure** coverage instead of claiming 80% | v2-0 |
| 5 | `pytest-cov` installed but unused; no test markers | `--cov` + `-m "not e2e"` | v2-0 |
| 6 | `pandas`, `streamlit`, `plotly` unused | delete | v2-0 |
| 7 | No seed/demo mode, so `make smoke` needs live Garmin credentials and no reviewer can run it | `make seed DAYS=400` from existing fixtures | v2-0 |
| 8 | Hand-written TS types duplicating Pydantic schemas | generate the client from OpenAPI + a drift check | v1 |
| 9 | No frontend lint/format/tests | add the minimum that CI can enforce | v1 |
| 10 | Review gates exist as a registry but nothing reads it | port the review-attestation gate, or delete the pretence | v1 |
| 11 | `specs/SEC-001` unarchived after merge | adversarial review + archive | v1 |
| 12 | Duplicate lessons SSOT (`lessons.md` + `lessons/`) | one SSOT, the index generated | v1 |
| 13 | ruff default ruleset; no `.editorconfig`; no devcontainer | align with the sibling repos | v2 (later) |
| 14 | No architecture diagram, screenshots or demo for reviewers | Mermaid + seeded screenshots | v2 (later) |

---

## 12. Instrumentation first — the measurements that decide things

Three measurements gate decisions, and all three are cheap. (Pass 1's M1 — the BLE advertisement scan —
is **cancelled**: it only existed to choose a BLE route, and SC-09 removed the BLE route from the MVP.)

| # | Measurement | Decides | How |
|---|---|---|---|
| **M4** | Weigh in with the phone **in another room**, then open the app: does the reading appear **with its original timestamp**? | whether the FitDays cloud can be the only scale path, or whether local capture is required (ADR-012) | 5 minutes, at home |
| **M5** | Does the owner's watch model support **Health Snapshot**, and does the pinned `garminconnect` expose it? | whether a 2-minute morning ritual can supply HRV/HR without sleeping with the watch (SC-06's optional add-on) | 10 minutes |
| **M6** | From a phone on 4G, does a tailnet-resolved name reach the app **through the tunnel** (source `100.64.x.x`), and does `vpn-whitelist` fail closed? | which of the two routes is the daily one (ADR-011), and whether `forwardAuth` can be trusted as a boundary | 15 minutes on staging |

Smaller checks that gate nothing but change what stays open behind the door: does the pinned
`garminconnect` expose the body-composition and weigh-in endpoints (a possible one-way mirror into
Garmin, never a source), and is the impedance field actually populated on existing readings (which
decides whether local BIA is ever worth building)?

---

## 13. Phased plan

Each phase is independently valuable and gated by the previous phase's telemetry — not a big-bang
rewrite.

| Phase | Content | Exit criterion (telemetry) |
|---|---|---|
| **0 — Substrate & hygiene** | LICENSE, `AGENTS.md`, pre-commit + gitleaks, CI permissions/concurrency, dead deps removed, migrations mechanism landed, **the v1→v2 migration of §4.1**, `activity_streams` table, `ingest_run` + `raw_payload`, atomic sync, date-filtered activities with backfill, timezone semantics per ADR-008 | the migration test upgrades a v1 fixture to v2 and asserts row counts and the TZ transformation, exercised against a copy of the real database first; coverage is **measured and recorded in CI**, which then fails if it falls more than 2 points below that baseline (a ratchet, not an invented 80%); `make seed` produces a populated DB with no credentials |
| **1 — Metric layer** | `derived_daily`, transparent readiness with contributors, HRV numeric series, sleep debt with a stated need | hand-computed fixture values match; `Today` renders contributors and coverage |
| **2 — Daily-use surface** | `/healthz` + the single ingest-health alarm, the **Sunday** Apprise review (SC-07), dashboard shell, accessibility and performance pass | 3 consecutive weekly reviews, each carrying data and an adjustment line |
| **3 — Private deployment** | kubelab prod, Authelia, SOPS, Postgres, backups, restore drill, promotion path | private URL reachable, break-glass exercised once, restore verified |
| **4 — Scale pillar** | cloud poller as primary (SC-09) → weight + body-composition tables → reconciliation → `Body` screen with the goal band | 14 consecutive weigh-ins captured with **no manual CSV import or data entry**, **and M4 passed** (a weigh-in with no phone present appears with its original timestamp); the reconciliation rule of ADR-012 documented and tested |
| **5 — Deferred, explicitly not in v2** | nutrition logging and the adaptive-intake loop (SC-01/SC-03); BLE capture as the remedy if M4 fails (SC-09); a static synthetic demo (SC-04); local LLM narration (SC-11) | each reopens as its own decision, never as a phase of this plan |

---

## 14. Risks and failure modes

| Risk | Detection | Mitigation |
|---|---|---|
| Garmin 429 / Cloudflare block | error rate on ingest runs | cadence discipline, backoff, token caching; intervals.icu as an optional secondary |
| Scale vendor changes its app, halting cloud ingest | ingest run failure; weigh-in gap | **the cloud is primary now, so this risk is live rather than theoretical.** M4 decides whether local capture is needed as the vendor-independent path; the poller sits behind an adapter, so a replacement route is a new adapter and not a rewrite |
| A reverse-engineered client is abandoned | dependency churn | isolate behind an adapter; never make it the only path |
| Body-composition numbers read as clinical | user confusion, or worse | trends with bands, algorithm-tagged rows, caveat line, no point values |
| Recommendation issued on thin data | review of `recommendation_log` | ≥5 logged days, capped adjustments, ranges, explicit "insufficient data" |
| LLM reads raw health series | token/context audit | not a risk v2 carries — no model participates (SC-11). If one ever does, bounded pre-aggregated windows only, and locally |
| Public URL exposes health data | edge + app logs, exposure review | two boundaries, no share routes in v1, derived-aggregates-only for any public surface |
| VPS resource pressure | kubelab quota watcher | 1 replica, modest requests, streams retention window |
| Ingestion silently stops (the classic) | `/healthz` staleness + Apprise alert | the one alert we do keep |
| Formula drift across versions | recompute reproducibility test | raw inputs retained; derived recomputed, never hand-edited |

---

## 15. Decisions taken, and the measurements that remain

Every decision that was open in pass 1 was answered with the owner on 2026-09-24; the register in
[`scope-interview.md`](scope-interview.md) holds the reasoning and the consequences.

| Was | Now | Register |
|---|---|---|
| D1 — where the private instance lives | **kubelab prod**, reachable through **two routes**: a tailnet route for daily use and a public route behind login + 2FA for devices that cannot join the mesh | SC-04 |
| D2 — which scale route | **cloud-first**, BLE only as the remedy; pending the M4 test | SC-09 |
| D3 — nutrition scope | **out of v2** | SC-01, SC-03 |
| D4 — private or public | **private**, single user, no subject column; a second person means a second instance | SC-04, SC-12 |
| D5 — goal mode | still open as a *product* choice, and it now matters more: `goals` is what makes the load↔body relationship readable. To be settled when the `Body` screen is designed | SC-03, SC-06 |
| D6 — readiness: mirror Garmin or replace it | **moot in the MVP** — Garmin's readiness is absent most days (SC-05), so the app does not compete with it; the recovery panel appears when data exists | SC-05, SC-06 |
| D7 — LLM coach | **none in v2**; supersedes ADR-005 in intent | SC-11 |

**Remaining measurements (not questions — tests to run):**

| # | Measurement | Decides | Cost |
|---|---|---|---|
| **M4** | Weigh in with the phone in another room; does the app show the reading with its **original timestamp**? | whether the cloud is truly primary, or whether BLE is needed after all | 5 minutes |
| **M5** | Does the owner's watch support **Health Snapshot**, and does the pinned `garminconnect` expose it? | whether a 2-minute morning ritual can replace overnight HRV (SC-06's optional add-on) | 10 minutes |
| **M6** | Does a phone on 4G reach a tailnet-resolved name **through the tunnel** (source `100.64.x.x`), and does `vpn-whitelist` fail closed? | route A's feasibility, and whether route B becomes the daily path instead | 15 minutes on staging |

**Settled earlier, for the record:** timezone semantics (UTC at rest, local calendar day for rollups —
ADR-008) and the licence posture (permissive code, private-only ODbL data if nutrition ever lands,
copyleft neighbours as separate processes — ADR-007).

---

## 16. Prior art — GitHub sweep, 2026-09-24

Run because the honest first question about this project is "has somebody already built it?". The answer
is **yes, three times over, in three different shapes** — and none of them is this product. Their repos
were cloned and read, not skimmed from a search result. Licences: MIT for `soma` (per its README badge);
the others ship a `LICENSE` whose kind was not opened, so it is unverified here.

| Project | Shape | What to take from it |
|---|---|---|
| **`drkostas/soma`** — the closest *product* | Next.js + Python bridge + Postgres + a real mobile app (Maestro e2e flows), Garmin · Hevy · Strava, MIT, live demo, screenshots | Its **information architecture**: `overview`, `running`, `sleep`, `calendar`, `workouts` — one calm page, then depth. Also `share-image.ts` (a shareable session card), `dedup.ts` + `token-store.ts` in the bridge (the same two problems this design solves), and — most stealable — a **`demo-drift` workflow** (`scripts/demo-drift.sql`, `verify-db-refresh.sh`) that keeps its seeded demo from drifting away from the real schema. That is the guard `make seed` should adopt |
| **`johnzastrow/garminview`** — the closest *architecture*, the closest to this design's own stack | FastAPI + SQLAlchemy + **Alembic (10 migrations)** + Vue 3, SQLite or MariaDB, `analysis/` package, GarminDB for downloads | A **validated module split for the metric layer**: `analysis/metrics/{training_load,body_composition,cardiovascular,sleep_science,composite_scores}.py` + `assessments/trend_classifier.py` + `energy_balance.py` — i.e. exactly the deterministic-engine-with-per-domain-modules shape of ADR-013, arrived at independently. It also added a **`source` column to `weight_body_composition` and to `sleep/rhr/vo2max` by migration** (0007, 0009), which is the same provenance decision this design took |
| **`arin-jaff/TrainingGeeks`** — the closest *dashboard ambition* | Next.js app-router + Tauri desktop, self-hosted, intervals.icu sync, live read-only demo on a Raspberry Pi | Its **page map as a menu of charts worth having**: `dashboard`, `calendar`, `metrics`, **`peaks`** (peak/pace-duration curves), **`progression`**, `routes`, `strength`, `activity/[id]`, **`atp`** (annual training plan), `workout-comparison`, `duplicates`. Per-sport PMC, and `publish-readonly-build.yml` — the pattern for publishing a read-only build, if a public demo is ever wanted |
| **`arpanghosh8453/garmin-grafana`** (3k★) | Garmin → InfluxDB → Grafana, two dashboards including weight/body composition | The **Grafana route** as a real alternative for the ops/exploration half. This design keeps Grafana for observation and a purpose-built frontend for the product (research brief 03), and this project is the evidence for why: its dashboards are powerful and have no narrative |
| **`jordanruthe/ble-scale-sync`** | Cross-platform CLI: 25+ BLE smart scales → **Garmin Connect**, Strava, Intervals.icu, MQTT, InfluxDB, webhooks, Ntfy, Telegram, CSV | **The remedy if M4 fails**, and a better one than hand-writing BLE: run it near the scale, let it push weigh-ins into Garmin Connect, and garsync reads Garmin as it already does. No custom BLE code, no protocol work. (Distinct from the `ble-scale-sync` cited in research brief 01 — two projects share the name) |
| **`cyberfossa/garth-relay`** · **`diegoscarabelli/garmin-health-data`** | FastAPI relay writing weight/BP **into** Garmin via garth · a Garmin health data exporter | The write-back path as a standalone service; and a **schema precedent**: `garmin-health-data` v2.8.0 stores body composition in a `body_composition` table **keyed by `(user_id, timestamp)` so multiple weigh-ins per day survive, insert-only with `ON CONFLICT DO NOTHING`** — which is what this design already chose (`UNIQUE(source, measured_at)`) and an argument against keying weight by day |

**The honest read.** None of these is the product this design describes, and the reason is narrow and
specific: they each own *one* of the four pieces (a dashboard, a bridge, an analysis engine, a Grafana
stack) and none owns the **join** — how body composition responds to accumulated training load, with the
goal band as the reference and every number traceable to a source row. `soma` comes closest and is
mobile-first with nutrition; `garminview` comes closest in architecture and offers no relationship view;
`TrainingGeeks` has the widest surface and is a training log, not a body-response tool. Two further
differences are deliberate here: the **weekly review plus one alarm** discipline instead of "check the
dashboard daily" (SC-07), and a **metric layer that refuses** the models which cannot be validated
(ADR-013).

**What this sweep changes**: nothing in the decisions, and three things in the plan — the metric layer's
module boundaries get a reference implementation to compare against, `make seed` gains a drift guard, and
ADR-012's remedy for a failed M4 becomes "run an existing bridge that writes into Garmin" rather than
"write a capture process".

---

## 17. Evidence base and what remains unverified

| Brief | Covers |
|---|---|
| `research/01-smart-scale-fitdays.md` | BLE families, open-source integrations, cloud clients, route ranking, reconciliation |
| `research/02-garmin-ingestion-and-realtime.md` | `garminconnect` status, developer program reality, aggregators, latency floors, workout push |
| `research/03-selfhosted-health-platforms.md` | build-vs-adopt, Endurain, migration/normalisation/idempotency/units mechanics |
| `research/04-training-analytics-and-coaching.md` | load models, readiness, streams gap, metric→source mapping and value ranking |
| `research/05-nutrition-and-body-composition.md` | BIA accuracy, adaptive expenditure, smoothing constants, v1 metric set |
| `research/06-access-privacy-and-sharing.md` | auth options, GDPR for a single data subject, sharing, multi-user cost |
| `research/07-ux-dx-packaging-and-delivery.md` | dashboard IA, digest cadence, PWA limits, DX gaps, accessibility |

**Unverified, and therefore not relied upon:** whether kubelab's Traefik forward-auth fails closed
(test it on staging); whether the Hetzner node's disk is encrypted at rest; whether passkeys work from
an installed PWA on the owner's phone; the exact FitDays behaviour for offline-buffered weigh-ins;
whether Wi-Fi Fitdays models exist; the current Google Fit deprecation timeline. Each of these is
either measured in phase 0–4 or explicitly excluded from the design.

**Two review passes are done.** An independent review by `nan/mimo-v2.5` — not the authoring model — is
recorded in [`review-v2-pass1.md`](review-v2-pass1.md) with the adjudication of each finding: one Blocker
acknowledged and fixed, one downgraded after reading the ODbL text that settled it, and one rejected with
reasons. Pass 3 then locked the scope with the owner. No ticket has been opened yet, deliberately.
