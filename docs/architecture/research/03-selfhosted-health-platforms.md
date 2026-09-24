# 03 — Self-hosted health & fitness platforms: what exists, what to copy, what not to adopt

**Bottom line.** There is no open-source backbone that covers Garmin training *and* recovery *and* body composition *and* diet for one athlete, so the question "adopt or build" is already answered by the field: the projects that got close either stopped at one vertical (openScale = scale, Gadgetbridge = devices, wger = workouts/nutrition, GoldenCheetah = cycling analysis) or died of the weight of being a general health platform (Fasten OnPrem is now explicitly unable to import provider data). The single most instructive finding is **Endurain** — a self-hosted fitness service built on *exactly garsync's stack* (FastAPI + SQLAlchemy + Alembic + PostgreSQL + `python-garminconnect` + Apprise), AGPL-3.0, 2.2k stars, which has synced Garmin activities, gear **and body composition** for years and which its solo maintainer put under a **temporary feature freeze on 2026-05-23** to repair module boundaries, background jobs and "the reliability of imports, syncs, and maintenance tasks". That is the honest read of the category: the problems garsync is about to meet (idempotent sync, dedup, unit drift, schema evolution) are the same ones that forced a mature project to stop shipping features — so the right move is to *keep a purpose-built single-user app* and steal the proven mechanics (unit contract, per-source handler registry, Alembic migrations, UPSERT-shaped idempotent ingestion, a metric registry with FHIR-style codes but not a FHIR server), rather than wrap Medplum/HAPI/openEHR or fork a PHR.

All access dates: **2026-09-24** (fetched live, not from cache).

---

## Findings

### 1. Endurain is the closest credible backbone — and the clearest warning (MEASURED)

- Repo: `endurain-project/endurain` on GitHub is a **read-only mirror**; canonical development is `https://codeberg.org/endurain-project/endurain` (`has_issues: false`, `has_pull_requests: false` on the mirror). **AGPL-3.0-or-later**, Python, created 2023-10-26, last push **2026-09-09**, 2,214 stars (mirror), 109 open issues. [GitHub API](https://api.github.com/repos/endurain-project/endurain)
- Stated stack, verbatim from the docs home: "Backend: Python FastAPI, Alembic, SQLAlchemy, Apprise, stravalib and **python-garminconnect** for Strava and Garmin Connect integration, gpxpy, tcxreader and fitdecode for .gpx, .tcx and .fit file import"; "Database: PostgreSQL"; "Observability: Jaeger for basic tracing". [docs.endurain.com](https://docs.endurain.com/)
- Feature list confirms the overlap with the target design: **multi-user**, activity import (`.fit` preferred), "Garmin Connect integration for syncing **activities, gear and body composition**", "**Weight, steps and sleep logging**", gear + gear-component usage, goals, notification system, MFA TOTP, **SSO (OIDC/SAML)**, "Imperial and metric units support", "Third-party app support". [docs.endurain.com](https://docs.endurain.com/)
- The generated API reference shows the data model garsync would be reproducing anyway: a `health_weight` module ("user weight and body composition… BMI, body composition metrics"), a `health_sleep` module ("sleep duration, stages, quality metrics, heart rate, SpO2, and sleep scoring", with `Source`, `SleepStageType` enums), and `activity_streams` (HR, power, cadence, elevation, speed, pace, map) with `create_activity_streams` / `transform_activity_streams`. [docs.endurain.com/reference](https://docs.endurain.com/reference/health/health_weight/)
- **Adoption risk, self-documented.** The 2026-05-23 post "Pausing new features so Endurain can keep growing" says the codebase "has reached a point where adding more features without first strengthening the foundations would make the project harder to maintain", that parts "grew organically… especially one maintained mostly by one person in spare time", and lists the repair targets: "Separating responsibilities between modules more clearly. **Reducing process-local state that can behave inconsistently in some deployments. Making scheduled and background work more predictable. Improving the reliability of imports, syncs, and maintenance tasks.**" New major integrations are explicitly deferred. [blog post](https://docs.endurain.com/blog/2026/05/23/pausing-new-features-so-endurain-can-keep-growing/)
- Also relevant: the docs' "Developer's note" states the maintainer is "a non-professional developer" who built the project "learning… new technologies and concepts, with invaluable assistance from GitHub Copilot and ChatGPT", and there is a **trademark** policy on the name/logo (personal self-hosting is fine, commercial hosting is not). Neither is disqualifying; both are inputs to a "who do I depend on" judgement. [docs](https://docs.endurain.com/) · [README `TRADEMARK.md`](https://raw.githubusercontent.com/endurain-project/endurain/master/README.md)
- **Failure mode:** operational weight is low (one Docker image + Postgres), schema rigidity is low-medium (Alembic), **abandonment/bandwidth risk is the real one** — one maintainer, on Codeberg, freeze in force, no PRs on the mirror.

### 2. wger: the workout/nutrition SSOT, not a telemetry sink (MEASURED)

- `wger-project/wger`, **AGPL-3.0-or-later** (README's own licence section: "Application Code: AGPL-3.0-or-later; Exercise/Ingredient Data: Creative Commons; Documentation: CC-BY-SA-4.0"), Python/Django, created 2013, last push **2026-09-22**, 6,960 stars, 252 open issues, 1,022 forks. [GitHub API](https://api.github.com/repos/wger-project/wger) · [README](https://raw.githubusercontent.com/wger-project/wger/master/README.md)
- Scope from README: custom routines with "automatic weight progression rules", "Track diet plans, body weight, and **custom measurements**", nutrition logging against **Open Food Facts**, progress photos, exercise wiki, cross-platform Flutter apps (Play/iOS/F-Droid/Flathub), "Powerful **REST API**", "**Multi-User Support**… basic gym management", self-hostable via `docker compose up`.
- Note what is *absent* from its own feature list: no device ingestion, no activities/telemetry, no recovery metrics. wger is a **plan-and-log** system (what you will do, what you ate, what you weigh), which is precisely the half garsync does not have. Its nutrition data is the reusable asset: the Open Food Facts dependency plus a per-user food log — do not rebuild a food database.
- **Failure mode for a solo operator:** adopting wger means inheriting Django + a multi-user gym-management model + a shared community exercise/ingredient corpus with its own licensing (CC for content), for a feature set (routines, 1RM progression) that garsync would have to re-implement in the dashboard anyway. Schema evolution is Django-migrations-standard, i.e. solved.

### 3. openScale + openScale-sync already solve the bathroom scale — including the unit contract (MEASURED)

- `oliexdev/openScale`, **GPL-3.0**, Kotlin, created 2014-12, last push **2026-09-22**, 2,554 stars, 526 forks, only **7 open issues** (a maintainer who closes triage, not a backlog graveyard). [GitHub API](https://api.github.com/repos/oliexdev/openScale)
- Extension model is the pattern to copy: a **per-model Bluetooth handler** plus a capability matrix. The "Supported scales in openScale" wiki is a table of `Scale | Handler | Connection | Body metrics | History data | Live weight | Time sync | User sync | Unit config | Battery | Remarks`, and the wiki "How to support a new scale" describes the two-step process: reverse-engineer the protocol, then implement a `ScaleDeviceHandler`. [wiki table](https://github.com/oliexdev/openScale/wiki/Supported-scales-in-openScale) · [how-to](https://github.com/oliexdev/openScale/wiki/How-to-support-a-new-scale)
- `oliexdev/openScale-sync` (GPL-3.0, separate APK) is the egress bus: "Synchronize your openScale measurements with external services… **Health Connect, Wger, Endurain, InfluxDB, generic Webhooks and MQTT (versions 3.1 and 5.0, including Home Assistant discovery)**", with **two-way** import per service ("export only, import only, or both"), automatic retry of undelivered syncs, optional periodic reconciliation "as a safety net for when the instant sync could not run", on-demand full sync, and multi-user awareness. [README](https://raw.githubusercontent.com/oliexdev/openScale-sync/master/README.md)
- **The unit contract, verbatim and worth stealing:** "Weight is synced in kilograms (kg). Body fat, muscle mass, and body water are all synced in percent (%). **Conversions to other units must be handled by the receiving program.**" That single sentence is the whole discipline garsync currently lacks: a declared canonical unit per metric, at the boundary, with conversion pushed to the consumer.
- It also names Endurain and wger as first-class sinks — i.e. the three "backbones" are already interoperating through one thin Android bridge, which is evidence that a **push-to-MQTT/webhook** ingestion edge is a viable integration seam for garsync without owning any of them.
- **Failure mode:** it is a phone app, not a server. There is no scale→server path that does not go through an Android device; openScale's own sync engine is the ceiling. FitDays support for the specific unit is **not verified** (see Gaps).

### 4. Gadgetbridge: real Garmin coverage, but it is a phone-side vendor-app replacement, not a backend (MEASURED)

- Canonical: `codeberg.org/Freeyourgadget/Gadgetbridge`. The GitHub org copy is a **stale mirror** (last push 2024-12-23, `has_issues: false`) — a trap for anyone assessing "is it dead?" from GitHub alone. Codeberg repo: Java, **1,936 stars**, 663 forks, **1,354 open issues, 134 open PRs, 13 releases**, active (repo `updated_at` 2026-09-24). [Codeberg API](https://codeberg.org/api/v1/repos/Freeyourgadget/Gadgetbridge) · [GitHub mirror API](https://api.github.com/repos/Freeyourgadget/Gadgetbridge)
- Licence: the root `LICENSE` is the **GNU Affero General Public License v3** text. [raw](https://codeberg.org/Freeyourgadget/Gadgetbridge/raw/branch/master/LICENSE)
- Coverage, from their own breakdown: "**615 gadget models from 82 different vendors**", split 182 working-well / 198 mostly / 100 partially / 7 pair-only / 128 unknown-support. [gadgetbridge.org/gadgets](https://gadgetbridge.org/gadgets/)
- **Garmin is supported and it is documented as such**: a dedicated page lists Fenix 2→6S/7/Epix/Enduro/Descent models, marked "**Experimental**… support for some of these devices is recent, and still experimental. This page is also still a work in progress and not complete"; the FAQ says Garmin watches "have also seen recent support… as of version 0.81.0. They are partially / mostly supported, depending on the model… **Unlike a lot of devices, they do not require the official app at all**." [Garmin devices](https://gadgetbridge.org/basics/topics/garmin/) · [FAQ](https://gadgetbridge.org/faq/best-device/)
- **Why it is still the wrong backbone:** storage is a local SQLite DB on the handset; there is no server, no HTTP API for third parties, and the ingest model is BLE-pairing-driven from the watch. Its value to garsync is *conceptual* (device handler registry, per-feature capability matrix per model) and *tactical* (if Garmin Cloud API access ever breaks, Gadgetbridge is the escape hatch — but on a watch, not on a scale).

### 5. Fasten OnPrem is the canonical dead end for "adopt a PHR" (MEASURED)

- `fastenhealth/fasten-onprem`, ~2,789 stars (GPL, **CLAIMED** — the root `LICENSE` returned 404, licence taken from the repo listing). [repo](https://github.com/fastenhealth/fasten-onprem)
- The README carries a warning that settles the question: "**Fasten Onprem is not able to import data from healthcare providers directly. You can only use this application to manually enter data, or upload FHIR Bundles that have been exported though other means.**" and "this open-source repo does not include any of the hosted infrastructure… it does not integrate with EHRs directly." [README](https://raw.githubusercontent.com/fastenhealth/fasten-onprem/main/README.md)
- An open issue dated 2026-02-07, "Fasten Onprem Update: Direct EHR Integrations Broken & Will Be Removed", states the open-source repo "has fallen out of sync" with the commercial stack. (**CLAIMED** — read from search snippet, issue body not fetched.) [issue #629](https://github.com/fastenhealth/fasten-onprem/issues/629)
- **Failure mode:** the differentiating feature (provider integration) required commercial infrastructure; what remains is a FHIR-bundle viewer. This is the shape of the risk for any "free tier of a company" backbone.

### 6. Medplum and HAPI FHIR: correct standards, wrong scale for one user (MEASURED for repo facts)

- **Medplum** `medplum/medplum`, **Apache-2.0**, TypeScript, created 2021-04, last push **2026-09-23 (same day)**, 2,701 stars, 672 open issues. Self-described surface: Medplum Auth (OAuth/OpenID/**SMART-on-FHIR**), Clinical Data Repository, FHIR API, SDK, web App, **Bots** ("write and run application logic server-side"), React UI component library. The README is candid about the blast radius: "this codebase isn't your typical open-source project because it's not a library or package with a limited scope — **it's our entire product**." [API](https://api.github.com/repos/medplum/medplum) · [README](https://raw.githubusercontent.com/medplum/medplum/main/README.md)
- **HAPI FHIR** `hapifhir/hapi-fhir`, **Apache-2.0**, Java, last push **2026-09-24**, 2,407 stars, 1,503 forks, **1,610 open issues** — it is a server/framework you embed in a Java service, not an application; adopting it means adopting a JVM service, a persistence layer, and FHIR's resource semantics. [API](https://api.github.com/repos/hapifhir/hapi-fhir)
- **Open Health Stack (OHS)** is now an umbrella foundation (`github.com/ohs-foundation`, described as "an umbrella project hosted within the Linux Foundation"); its examples repo `ohs-foundation/fhir-app-examples` is **Apache-2.0** with 57 stars, and the programme's own framing is "building blocks… **designed for low-resource settings** (e.g. off-line capable…) for **healthcare workers**". That is community-health-workforce tooling, not personal quantified-self. (**CLAIMED** — org/README text from search results, not read in full.) [ohs-foundation](https://github.com/ohs-foundation) · [Google OHS overview](https://developers.google.com/open-health-stack/overview)
- **What FHIR is actually worth to garsync: the vocabulary, not the server.** FHIR R4 carries a dedicated **"Ucum"** page inside its terminologies/Using-Codes section — i.e. units on quantity values are a normative part of the spec — and observation identity is a code from an external system rather than a column name. [hl7.org/fhir/R4/ucum.html](https://www.hl7.org/fhir/R4/ucum.html) Copy that triple (`system:code` identity + UCUM unit + effective timestamp) into one garsync table; do not run a FHIR server to get it.
- **openEHR** is heavier still: the Archetype Model component is at Release 2.3.0 with **ADL2** (an authoring language), **AOM2** ("full computable model of Archetypes and Templates… formally testable validity conditions") and **OPT2** operational templates. Modelling your body-fat measurement as a formally validated archetype is a research project, not a Saturday. [specifications.openehr.org/releases/AM/latest](https://specifications.openehr.org/releases/AM/latest/index.html)
- **Failure mode:** operational weight (a second platform, with users/tenants/projects/bots), schema rigidity (everything becomes a Resource; your Garmin-specific fields become Extensions), and for a single user, **zero interoperability benefit today** — you have no second system to talk to.

### 7. Home Assistant: the ingestion/statistics shape is the best free pattern in the set (MEASURED)

- `home-assistant/core`, **Apache-2.0**, Python, last push **2026-09-23**, **91,123 stars**, 38,744 forks — the most actively maintained project audited here by an order of magnitude. [API](https://api.github.com/repos/home-assistant/core)
- The Recorder integration documents the loop garsync needs to formalise: "Every time an entity changes state… the recorder writes that change to the database", and "Many parts of Home Assistant rely on this stored data. The History and Activity panels, the graphs shown on dashboard cards, and **long-term statistics** all read from the database that the recorder maintains." [docs](https://www.home-assistant.io/integrations/recorder/)
- Two directly copyable ideas: (a) a **raw state-change store separated from a derived long-term statistics table** — which is exactly the `samples` vs `daily_metrics` split; (b) the fact that a scale measurement can arrive over **MQTT with Home Assistant discovery**, per openScale-sync, so HA is a plausible *transport*, not a *destination*, for garsync.
- **Failure mode:** HA's data model is entity-state centric (`entity_id`, `state`, `attributes`) and its history/statistics machinery is built for house-level sampling, not for per-athlete session analytics (training load, TSB, periodisation). Adopting HA as the health SSOT means fighting its abstraction; using it as one of several feeds costs almost nothing.

### 8. GoldenCheetah — desktop, GPL-2.0, and the metric-as-formula idea worth stealing (MEASURED for facts)

- `GoldenCheetah/GoldenCheetah`, **GPL-2.0**, last push **2026-09-23**, 2,205 stars, 474 forks, 54 open issues; a C++/Qt desktop application (GitHub's linguist reports "Standard ML", which is itself evidence of how little the repo is a web service). [API](https://api.github.com/repos/GoldenCheetah/GoldenCheetah)
- Relevance to garsync: GC is where the *analysis* layer lives for endurance athletes (models, charts, intervals, peak-power curves). It is not deployable as the kubelab service garsync is, and its storage is a per-athlete filesystem/crypt store, not a queryable server database. (**CLAIMED/INFERRED** — product surface asserted from its positioning; I did not read the code this session.)
- The pattern to take is **user-definable derived metrics** rather than hard-coded columns; intervals.icu's maintainer describes the same idea server-side: "I am trying to make it extensible using **Javascript run on the server** e.g. to calculate custom activity fields, create custom activity charts." [forum.intervals.icu](https://forum.intervals.icu/t/code-contribution-via-git/31938)

### 9. intervals.icu and Exist.io are not backbones — one is closed, one is unreachable (MEASURED)

- **intervals.icu is not open source.** Its GitHub org (`intervals-icu`) has **2 public repos** — `intervals-i18n` (localisation, 34 stars) and `js-data-model` ("Data model for Javascript code for custom Intervals.icu fields, charts, streams", 3 stars) — and the maintainer states directly: "I was not surprised to see that intervals.icu is not a public repository… **Intervals.icu is fairly complicated to run and work on and there are all sorts of data privacy issues so its not very amenable to open source.**" [org](https://github.com/intervals-icu) · [forum post](https://forum.intervals.icu/t/code-contribution-via-git/31938) Treat it as a *product spec* for what a Garmin analytics surface must do (streams, custom fields, wellness records, athlete/calendar/sport-settings API objects — visible in the community API clients), never as a dependency.
- **Exist.io**: `exist.io/documentation/` returned **HTTP 404** when fetched. Exist is a closed commercial service with a coach-facing metric feed; I could not verify a current API doc from the primary source. (**GAP** — do not cite Exist as a design precedent in the repo docs without a live source.)

### 10. The quantified-self new wave converges on exactly garsync's shape (MEASURED via listing, CLAIMED via README)

- `BRO3886/healthsync`: "**Parse Apple Health exports into a local SQLite database** — queryable by AI agents, the CLI, or directly via SQL", Go, MIT, 64 stars, created **2026-02-12**, topics `apple-health cli golang health-data self-hosted sqlite tailscale`; claims a streaming parser that "Handles 950MB+ exports at constant ~10MB memory. 500k records in ~30 seconds", a CLI plus an HTTP server receiving uploads from iOS Shortcuts over Tailscale, and a shipped agent-skill describing the schema. [repo](https://github.com/bro3886/healthsync) · [docs site](https://healthsync.sidv.dev/)
- `megabyte0x/healthykit`: "a native SwiftUI iOS app that reads selected Apple Health data on-device through HealthKit and **syncs queued JSON batches to a private REST backend**" (FastAPI). [repo](https://github.com/megabyte0x/healthykit)
- Read together with openScale-sync, the 2025-26 pattern is stable and unanimous: **phone collects → push JSON batches to a self-hosted endpoint → land in SQLite/Postgres → query with SQL and an LLM over the schema**. Nobody in this cohort is running a message broker or a TSDB. That is a strong signal about what a solo operator actually needs.

### 11. Storage engines: a dedicated TSDB is not justified; the Postgres/SQLite question is a licensing-and-migrations question (MEASURED)

| Engine | Repo fact (2026-09-24) | Verdict for garsync |
|---|---|---|
| SQLite | UPSERT docs: "UPSERT is a clause added to INSERT that causes the INSERT to behave as an UPDATE or a no-op if the INSERT would violate a uniqueness constraint… **UPSERT is not standard SQL. UPSERT in SQLite follows the syntax established by PostgreSQL**, with generalizations." | Perfect for ≤ ~10⁶ rows/yr single-writer; **the identical idempotency primitive exists on both engines**, so the sync code does not change. |
| PostgreSQL (kubelab shared) | n/a | The right production target: it is already operated, backed, and connection-pooled for you; every mature project audited (Endurain, wger default prod, Medplum, HA optionally) runs on it. |
| TimescaleDB | `timescale/timescaledb`, C, last push 2026-09-23, **23,578 stars**; README: "TimescaleDB is a **PostgreSQL extension** for high-performance real-time analytics on time-series and event data". Licence is **split**: "Outside of the 'tsl' directory, source code… Apache License Version 2.0… Within the 'tsl' folder, source code… licensed under the **Timescale License**"; `-tsl` shared objects carry the TSL. | The interesting option *if* retention/compression matters, since it stays SQL. But at one athlete's volume, hypertables buy nothing that a `daily_metrics` table and a `DELETE` cron do not. |
| DuckDB | `duckdb/duckdb`, C++, last push 2026-09-23, **41,669 stars** | Not the primary store; the best **out-of-band analytics** attach (read Parquet snapshots, do cohort/periodisation math) without touching the OLTP engine. Licence not verified this session. |
| QuestDB / InfluxDB | `questdb/questdb` Java, 17,344 stars; `influxdata/influxdb` now reported language **Rust**, 31,754 stars — both pushed 2026-09-23 | Active projects, wrong shape: a second query language, a second operational surface, and no feature garsync needs at 1 user. InfluxDB's Rust rewrite is itself churn risk. Licences not verified this session. |

### 12. Queue plumbing: at-least-once + idempotent write is the whole game (MEASURED)

- **NATS JetStream**: "Core NATS delivers messages only to subscribers connected at the moment of publication — **at most once, never replayed**. JetStream adds a persistence layer on top, giving you **at-least-once delivery** — messages survive restarts and can be replayed." Consumers are "server-side, stateful view[s]… if a message isn't acknowledged in time, the server redelivers it." [docs.nats.io/nats-concepts/jetstream](https://docs.nats.io/nats-concepts/jetstream)
- **Redis Streams**: `XREADGROUP` gives consumer groups with a Pending Entries List: "the server will *remember* that a given message was delivered to you: the message will be stored inside the consumer group in what is called a Pending Entries List (PEL)… The client will have to acknowledge the message processing using `XACK`", and crash recovery is "read pending with an ID of 0 until the reply is empty, then switch to `>`". One-owner-per-message is the *partitioned* mode; without consumer groups every client sees every message. [redis.io/commands/xreadgroup](https://redis.io/docs/latest/commands/xreadgroup/)
- **The invariant both docs imply and Endurain's freeze proves:** at-least-once delivery is cheap and universal; therefore *the receiver must be idempotent or the pipeline is wrong*. That is a unique-index-plus-UPSERT requirement on the storage side, not a broker requirement. garsync already runs on Redis (kubelab) and Apprise; the correct first step is **an ingest ledger table + UPSERT**, and only later a broker.
- **MQTT** earns its place only as a device-facing edge (openScale-sync publishes MQTT 3.1/5.0 with Home Assistant discovery). NATS/Kafka at single-user volume is pure operational tax.

### 13. Dashboards: Grafana for observation, own frontend for the product (MEASURED)

- `grafana/grafana`, last push **2026-09-24**, **76,870 stars** — the default answer, and in kubelab it is already deployed with Loki/Vector. (Licence not verified this session; Grafana's AGPL move is widely known, so confirm before redistribution.) [API](https://api.github.com/repos/grafana/grafana)
- Metabase/Superset: not fetched this session — **gap**, but the judgement stands on shape: BI tools answer "aggregate over my table", which is a *different* question from "did my 4×4 hurt my sleep score", which is what garsync's dashboard is for.
- **Opinion:** the projects that own their UX (wger's Flutter app, Endurain's Vue 3 + Tailwind + shadcn-vue, intervals.icu) are the ones people actually self-host long-term. garsync's Astro-islands frontend is an asset, not a liability; Grafana should be mounted *behind* it for raw time-series spelunking, and as the operational view (Loki logs, ingest lag) — not as the product.

---

## Structural answer

**No, there is no credible open-source backbone to adopt or wrap. Build the single-user app; copy the mechanics.** The evidence is that the field has *already* decomposed the problem into the same four pieces garsync is assembling, and solved each one at the edge rather than in a platform: **device→app** (Gadgetbridge/openScale, per-model handler registries), **app→server** (openScale-sync push to MQTT/webhook/Health Connect with a declared unit contract), **activity analytics** (Endurain/intervals.icu/GoldenCheetah, proprietary or server-adjacent), and **plan/nutrition** (wger against Open Food Facts). No project owns the join across those four, which is exactly the value of the app being designed — and every attempt to buy a general health backbone (FHIR platforms, PHRs, openEHR) imports multi-tenant clinical machinery whose interoperability payoff is zero for one patient and one consumer.

**Where the mature projects solved the four hard problems, and what to copy:**

1. **Schema evolution** — Endurain uses **Alembic** (explicitly listed in its stack); wger inherits Django migrations. garsync currently has **no migration tool at all** (`pyproject.toml` dependencies are `garminconnect, pydantic, tenacity, typer, rich, pandas, streamlit, plotly, fastapi, uvicorn` — no SQLAlchemy, no Alembic), so adding one before the metric surface grows is the highest-leverage structural change available. Add SQLAlchemy 2.0 + Alembic, or a numbered-`.sql` runner; never hand-edit a schema that exists in two environments.
2. **Metric normalisation** — Endurain's generated reference exposes named modules per concern (`health_weight`, `health_sleep`, `activity_streams`) with **enums for `Source` and `SleepStageType`**; openScale encodes a per-metric capability matrix; FHIR encodes identity as `system:code` plus UCUM units. garsync should hold a `metric` registry (code, canonical unit, source, value type, aggregation rule) and a narrow `sample` table for everything that is not one of the ~15 hot columns.
3. **Idempotent ingestion & dedup** — the whole category is built on at-least-once delivery (NATS/Redis docs above; Endurain's freeze list literally includes "improving the reliability of imports, syncs, and maintenance tasks"), which forces *natural-key uniqueness + UPSERT*. SQLite and Postgres share that syntax family, so: `UNIQUE(source, source_activity_id)` for activities, `UNIQUE(user_id, metric_code, ts)` for samples, `DO UPDATE SET … WHERE excluded.received_at > …` semantics, plus an append-only `ingest_run` watermark table so a re-pull is safe and observable.
4. **Unit handling** — the best available contract is openScale-sync's one-liner (canonical kg / %, conversion is the *receiver's* job). Adopt it verbatim in spirit: store canonical SI-ish units, never store display units, convert at the edge, and pin the contract in a test.

**Failure-mode summary for each candidate backbone** (the three axes asked for):

| Backbone | Operational weight | Schema rigidity | Abandonment risk |
|---|---|---|---|
| Endurain | Low (1 container + Postgres) | Medium (typed tables; Alembic keeps it moving) | **High-ish**: solo maintainer, Codeberg-only, feature freeze, trademark on the name |
| wger | Medium (Django + workers + Flutter clients) | Medium; "custom measurements" is the escape valve | Low-medium (13 years old, 6.9k stars, pushed 2026-09-22, funded-ish) |
| openScale (+sync) | Low, but requires an always-on Android handset | Low (per-model handler registry is the extensibility answer) | Low-medium (single maintainer, but 7 open issues and a 2026-09-22 push) |
| Gadgetbridge | Low for the user, zero for the server (there is none) | Medium (per-vendor feature matrix) | Low (large distributed community, AGPL, active on Codeberg) |
| Fasten OnPrem | Medium | High (FHIR bundles) | **Realised**: provider import withdrawn/removed |
| Medplum / HAPI | **High** (a platform, or a JVM service + persistence) | High (everything is a Resource; device specifics become Extensions) | Low (Apache-2.0, VC-backed / clinical-industry standard) |
| Open Health Stack / openEHR | High | Very high (archetypes, ADL2, templates) | Low as a standard, irrelevant for personal use |
| Home Assistant | Medium (already running?) | High for health semantics (entity-state model) | Very low (91k stars, daily pushes) |
| GoldenCheetah | None (desktop) | N/A — per-athlete file store | Low (active 2026-09-23) |

---

## What this means for garsync

1. **Do not adopt a backbone. Stay purpose-built, single-user.** Every candidate either lacks the Garmin half, the scale half, or the loop. The portfolio-grade story is "I closed the loop between training, recovery, body composition and diet", not "I deployed FHIR".
2. **Change the engine before the schema grows.** Postgres on kubelab (shared instance, existing backups) as the production target, SQLite retained as the dev/test path. Both sides of that decision are cheap *only* because UPSERT is common to both engines (Finding 11). If you deploy to nan Builders Basic Space instead — env vars only, 20 GiB — keep SQLite on the PVC and accept the ceiling; do not run your own Postgres container there.
3. **Adopt Alembic + SQLAlchemy Core/2.0 now**, mirroring Endurain's proven combination. This is the one change that is strictly cheaper today than after the scale and diet tables land.
4. **Copy openScale-sync's unit contract into a doc + test, and publish an MQTT/webhook sink that matches it.** Then the scale path becomes: FitDays app → openScale (if the model is supported) → openScale-sync → **MQTT in kubelab** → garsync consumer. garsync stays a receiver of canonical kg/%, with zero BLE protocol work.
5. **Do not reverse-engineer the FitDays BLE protocol or its cloud API in this repo.** That is exactly the kind of asset that becomes a personal liability (and Fasten's arc shows what happens when a project's ingest depends on someone else's closed endpoint). If openScale has no handler, contributing one upstream is a *better portfolio artifact* than a private scraper, and it reuses their `ScaleDeviceHandler` capability-matrix design.
6. **Ingestion design: ledger + watermark + UPSERT, not a broker.** Add `ingest_run(source, cursor, started_at, finished_at, status, rows_upserted)` and a `raw_payload` table (JSON, retention-limited) so any Garmin/scale response can be replayed after a schema change — the "reduced process-local state / predictable background work" that Endurain had to spend a freeze learning. Redis Streams or NATS only enter the picture when a second consumer or device pushes.
7. **Metric registry, FHIR-flavoured, no FHIR server.** One small table: `code`, `system` (e.g. `garsync`, `garmin`, `loinc` where a real code exists), `unit` (UCUM), `dtype`, `agg`, `polarity`. This buys clean normalisation and a trivially documentable public API, at ~200 LOC, instead of a resource server.
8. **Use the ecosystem for what each does best.** Garmin analytics stays yours (Endurain/intervals.icu as *specs*, not deps). Nutrition: log against **Open Food Facts** the way wger does; do not build a food DB. Recovery dashboards: your Astro islands. Ops/telemetry view: Grafana pointed at Postgres + Loki, behind Authelia.
9. **Borrow intervals.icu's extensibility idea, not its code.** Server-side user-defined formulas over activity fields is the feature that keeps a quant app alive for years; implement it as a sandboxed expression evaluator over the metric registry, never as arbitrary JS.
10. **AGPL is a live decision, not a footnote.** wger, Endurain, openScale (GPL) and Gadgetbridge (AGPL) are all copyleft. Copying *patterns and unit contracts* is safe; copying code obliges garsync accordingly. If this repo is meant to stay permissive/proprietary-clean, state that in `docs/adr/` now and keep upstream code out of the diff.

## Open questions and decisions needed

| # | Question | Options | Decision owner |
|---|---|---|---|
| D1 | Does openScale support the specific FitDays scale model? | verify wiki/handler list → adopt; else contribute a handler upstream; else poll fitdays.app with credentials; else drop body-composition | Manu (blocks the scale pillar) |
| D2 | Production engine + home | (a) Postgres on kubelab, (b) SQLite on nan Builders PVC, (c) SQLite locally + Postgres later | Manu |
| D3 | Migration tooling | SQLAlchemy 2.0 + Alembic (Endurain-proven) vs a hand-rolled numbered-SQL runner | Manu |
| D4 | Endurain relationship | ignore (patterns only) / run it as activity+gear SSOT and let garsync be the analytics+loop layer / import its data | Manu — note freeze + solo maintainer |
| D5 | Inbound transport for the scale | direct POST from openScale-sync webhook / MQTT topic in kubelab / both | Manu |
| D6 | Metric identity vocabulary | garsync-native codes only, or LOINC where a defensible code exists | Manu |
| D7 | Licence posture w.r.t. AGPL/GPL neighbours | keep proprietary/Apache and copy only ideas, or relicense AGPL to accept upstream code | Manu |
| D8 | Auth | Authelia OIDC at the edge (kubelab) vs the in-app session work already ticketed (SEC-002/003/004) | Manu |

## Gaps (stated, not filled)

- **FitDays ↔ openScale compatibility: unresolved.** The "Supported scales in openScale" wiki was located but its rows were not read; the FitDays vendor docs confirm only that their scales are BLE/GATT devices. Must be checked by reading the wiki table or the `core/bluetooth/scales/` handler directory.
- **Exist.io: no primary source reachable** (`exist.io/documentation/` → 404). Not usable as a precedent.
- **Licences not verified this session:** DuckDB, QuestDB, InfluxDB, Grafana, Metabase, Superset; Fasten's licence (root `LICENSE` 404s) is taken from the repository listing.
- **GoldenCheetah internals (storage layout, formula engine) not read** — its role here is pattern-level, and that is flagged CLAIMED/INFERRED in Finding 8.
- **Home Assistant's default database and retention behaviour** were not confirmed from the fetched page; the recorder's *role* was. Do not state "HA defaults to SQLite" in repo docs without a source.
- **Search budget:** six provider requests were spent on name resolution (openScale/Medplum/HAPI/Fasten/OHS/intervals.icu/healthsync); the "recent self-hosted personal health data lake" sweep therefore sampled only the Apple-Health cluster (`healthsync`, `healthykit`) and is not exhaustive. A follow-up pass on `awesome-selfhosted` health entries would close it.

## Sources

Accessed 2026-09-24 (UTC). Primary sources preferred throughout; GitHub/Codeberg API responses used for stars, licence and last-push facts.

**Platforms**
- wger repository API — https://api.github.com/repos/wger-project/wger
- wger README (licence split, features) — https://raw.githubusercontent.com/wger-project/wger/master/README.md
- Endurain mirror API — https://api.github.com/repos/endurain-project/endurain
- Endurain README / Codeberg pointer / stack — https://raw.githubusercontent.com/endurain-project/endurain/master/README.md
- Endurain docs home (features, developer's note) — https://docs.endurain.com/
- Endurain feature-freeze post, 2026-05-23 — https://docs.endurain.com/blog/2026/05/23/pausing-new-features-so-endurain-can-keep-growing/
- Endurain `health_weight` reference — https://docs.endurain.com/reference/health/health_weight/
- openScale repository API — https://api.github.com/repos/oliexdev/openScale
- openScale wiki: supported scales — https://github.com/oliexdev/openScale/wiki/Supported-scales-in-openScale
- openScale wiki: how to support a new scale — https://github.com/oliexdev/openScale/wiki/How-to-support-a-new-scale
- openScale-sync README (backends, unit contract, retry) — https://raw.githubusercontent.com/oliexdev/openScale-sync/master/README.md
- Gadgetbridge Codeberg API — https://codeberg.org/api/v1/repos/Freeyourgadget/Gadgetbridge
- Gadgetbridge GitHub mirror API (stale mirror) — https://api.github.com/repos/Freeyourgadget/Gadgetbridge
- Gadgetbridge AGPLv3 LICENSE — https://codeberg.org/Freeyourgadget/Gadgetbridge/raw/branch/master/LICENSE
- Gadgetbridge device breakdown — https://gadgetbridge.org/gadgets/
- Gadgetbridge Garmin devices page — https://gadgetbridge.org/basics/topics/garmin/
- Gadgetbridge FAQ ("best device") — https://gadgetbridge.org/faq/best-device/
- Fasten OnPrem repo — https://github.com/fastenhealth/fasten-onprem
- Fasten OnPrem README (import limitation) — https://raw.githubusercontent.com/fastenhealth/fasten-onprem/main/README.md
- Fasten issue #629 — https://github.com/fastenhealth/fasten-onprem/issues/629
- Medplum repository API — https://api.github.com/repos/medplum/medplum
- Medplum README — https://raw.githubusercontent.com/medplum/medplum/main/README.md
- HAPI FHIR repository API — https://api.github.com/repos/hapifhir/hapi-fhir
- Open Health Stack org — https://github.com/ohs-foundation ; Google OHS overview — https://developers.google.com/open-health-stack/overview
- Home Assistant core API — https://api.github.com/repos/home-assistant/core
- Home Assistant Recorder integration docs — https://www.home-assistant.io/integrations/recorder/
- GoldenCheetah repository API — https://api.github.com/repos/GoldenCheetah/GoldenCheetah
- intervals.icu GitHub org — https://github.com/intervals-icu
- intervals.icu forum, maintainer on open-sourcing — https://forum.intervals.icu/t/code-contribution-via-git/31938
- healthsync (Go + SQLite, Apple Health) — https://github.com/bro3886/healthsync · https://healthsync.sidv.dev/
- healthykit (SwiftUI + FastAPI) — https://github.com/megabyte0x/healthykit

**Standards & storage/plumbing primitives**
- FHIR R4 "Ucum" page — https://www.hl7.org/fhir/R4/ucum.html
- openEHR Archetype Model, Release 2.3.0 index — https://specifications.openehr.org/releases/AM/latest/index.html
- SQLite UPSERT — https://www.sqlite.org/lang_UPSERT.html
- TimescaleDB repository API — https://api.github.com/repos/timescale/timescaledb
- TimescaleDB README — https://raw.githubusercontent.com/timescale/timescaledb/main/README.md
- TimescaleDB LICENSE (Apache outside `tsl/`, Timescale License inside) — https://raw.githubusercontent.com/timescale/timescaledb/main/LICENSE
- NATS JetStream concepts (at-least-once, server-side consumers) — https://docs.nats.io/nats-concepts/jetstream
- Redis `XREADGROUP` (PEL, XACK, claim, crash recovery) — https://redis.io/docs/latest/commands/xreadgroup/
- QuestDB / InfluxDB / DuckDB / Grafana repository APIs — `https://api.github.com/repos/{questdb/questdb, influxdata/influxdb, duckdb/duckdb, grafana/grafana}` (stars and last-push only)