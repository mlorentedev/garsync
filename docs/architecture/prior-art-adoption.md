---
id: "garsync-prior-art-adoption"
type: architecture
status: draft
created: "2026-09-24"
owner: manu
tags: [garsync, v2, prior-art, borrow-list]
source_sweep: "2026-09-24, repos cloned and read"
---

# Prior art → adoption list

> Every item below was read in a **cloned** repository, not skimmed from a search result. The licence
> column is not decoration: it decides whether the item is copied as **code** or taken as an **idea**.
>
> | Source | Licence | Path allowed |
> |---|---|---|
> | `drkostas/soma` | **MIT** | copy code, with attribution |
> | `arin-jaff/TrainingGeeks` | **AGPL-3.0** | ideas only — copying code would relicense garsync |
> | `johnzastrow/garminview` | **no LICENSE** (all rights reserved) | ideas and public formulas only, no fragments |
> | `arpanghosh8453/garmin-grafana` | GPL-family (unverified in detail) | ideas only, no code |
> | `jordanruthe/ble-scale-sync`, `cyberfossa/garth-relay` | unverified | run as a separate process, never vendor |
>
> **"Copy" for a MIT source still means reimplement in our stack**, not paste: their stack is
> TypeScript/Next.js and ours is Python + Astro. What transfers is structure, naming, thresholds and IA.

---

## A. Information architecture and UX

| Item | Source | Kind | How it lands here |
|---|---|---|---|
| **`overview` as one calm page**, then depth: `running`, `sleep`, `workouts`, `calendar` | soma | idea | Confirms the `Today`-first decision (§11 of the design). Our five screens map onto theirs minus workouts-specific muscle maps |
| **Sync Hub** — a page that shows *what synced*, live pipeline state and errors | soma | idea | **New, and worth taking.** Our `ingest_run` ledger is currently backend-only; expose it as a `Sync` page (run history, cursor position, rows upserted, last error, last successful run per source). It is the cheapest possible answer to "is it working?", and it is also the operator view for M4 |
| **Shareable session card** (`share-image.ts`) | soma | MIT code / idea | Later. A rendered PNG of one session, for showing someone without giving them a login |
| **Screenshot set in the README** (`screenshots/{overview,running,sleep,workouts,calendar}.png`) | soma | idea | Phase 0 DX: screenshots generated from the seeded demo, not from real data |
| **Peaks page** — peak / pace-duration curves | TrainingGeeks | idea | `Trends`, once streams exist |
| **Progression page** | TrainingGeeks | idea | `Trends`: PB and best-effort tracking over time |
| **Per-sport PMC** | TrainingGeeks | idea | `Trends`: CTL/ATL/TSB split by sport, which matters if training mixes cardio and strength |
| **Method comparison** (`calc_*_methods` returning several estimates side by side) | garminview | idea | Reuse the pattern for VO2max / max-HR / fitness-age: show all methods rather than picking one silently. Same principle as algorithm-tagged body composition |
| **UX audit as a document, with S/M/L effort per item and module names** | TrainingGeeks | idea | Adopt the *form* for our own UX backlog |
| **Their friction list as a warning**: half the app reachable only by URL; stub pages linked from anywhere are dead ends | TrainingGeeks | idea (lesson) | Rule: every shipped screen is in the nav, and nothing ships as `ComingSoon` |
| **Runtime gate instead of a forked branch** (`TG_READONLY` gated at runtime; their `readonly-mode` branch caused permanent merge conflicts) | TrainingGeeks | idea (lesson) | Confirms SC-04: no second deployment and no branch for demo/read-only. The seed is a runtime mode |

## B. Metric layer

| Item | Source | Kind | How it lands here |
|---|---|---|---|
| **Module split**: `metrics/{training_load, body_composition, cardiovascular, sleep_science, composite_scores}` + `assessments/trend_classifier` | garminview | idea | Adopt as the **package layout** for our metric layer. Independently arrived at, so it validates ADR-013's shape |
| **`calc_trimp(duration_min, avg_hr, max_hr)`**, `calc_ewma_series(values, tau)` | garminview | public formula | Core of `MET-001`. EWMA with a configurable τ also serves the weight trend (α = 1 − exp(−1/τ)) |
| **`calc_monotony(daily_loads)`**, `calc_strain(weekly_load, monotony)` | garminview | public formula | In `MET-001` |
| **`calc_heart_rate_recovery(hr_at_end, hr_1min_post)`** | garminview | public formula | **Missing from our list and cheap**: a 1-minute post-exercise HR drop is a real fitness/recovery signal available from daytime data only — which matters because most nights have no watch (SC-05) |
| **`calc_cardiac_drift(first_half_ef, second_half_ef)`** | garminview | public formula | Our decoupling metric, stated as first-half vs second-half EF. Needs streams |
| **`calc_lbm`, `calc_ffmi`, `calc_weight_velocity(weights, days)`** | garminview | public formula | `MET-002`. FFMI is a better body-composition summary than raw fat % for someone training daily |
| **`calc_rhr_zscore`, `calc_hrv_cv`, `calc_readiness_composite(hrv, rhr, …)`** | garminview | public formula | `MET-004`, conditional on overnight data (SC-05). Their composite takes normalised inputs — the transparent-z-score shape ADR-013 requires |
| **`calc_acwr`, `calc_overtraining_risk`** | garminview | rejected | Already refused by ADR-013. Seeing a mature project ship both does not change the validation evidence |
| **`S³` — Strength Stress Score**: `duration_min × (M/1.5)`, `M = 1.0 + RPE/10` clamped to [1.0, 2.0], anchored so a moderate hour = 60 | TrainingGeeks | idea | **New, and it decides a gap we have not closed.** Strength work has no TSS without power or pace. If training includes lifting, this is the honest way to count it — at the cost of one subjective input per session (RPE) |
| **A methodology document stating how every number is calculated** (`docs/METHODOLOGY.md`) | TrainingGeeks | idea | Our auditability differentiator needs exactly this, and it doubles as the in-app "where does this come from" page |
| **Banister impulse-response as a library** (`banister` npm package) | soma | MIT, other stack | Not usable in Python, but confirms the model is implementable; our PMC is the same family with published constants |

## C. Data model and ingestion

| Item | Source | Kind | How it lands here |
|---|---|---|---|
| **`body_composition` keyed by `(user_id, timestamp)`**, multiple weigh-ins per day preserved, **insert-only with `ON CONFLICT DO NOTHING`** | `garmin-health-data` v2.8.0 | idea | Confirms `UNIQUE(source, measured_at)` and the refusal to key weight by day. Their insert-only choice differs from ours deliberately: we want `DO UPDATE` so a corrected reading replaces itself |
| **A `source` column added to `weight_body_composition` and to `sleep/rhr/vo2max` by migration** | garminview (migrations 0007, 0009) | idea | Independent confirmation of the provenance decision in ADR-009 |
| **Garmin token store + dedup as separate modules in the sync bridge** (`token-store.ts`, `dedup.ts`) | soma | MIT code / idea | Our `garminconnect` handles tokens; the separation is still the right shape for our adapters |
| **Sync runs as GitHub Actions cron + Vercel crons** | soma | idea, rejected | A real alternative to an always-on service, and rejected here: Action crons are delayed and skippable, secrets move into CI, and a 30-minute activity cadence is not what they are for. Recorded so it is not re-proposed |
| **`demo-drift` workflow: `scripts/demo-drift.sql` + `verify-db-refresh.sh` keep the seeded demo from drifting from the real schema** | soma | idea | **Adopt.** It is the guard our `make seed` needs: a test that fails when the seed no longer matches the migrated schema |
| **`publish-readonly-build.yml` — a published read-only build** | TrainingGeeks | idea | The pattern for a public surface if one is ever wanted (SC-04 keeps it out of v2) |

## D. Delivery, ops and DX

| Item | Source | Kind | How it lands here |
|---|---|---|---|
| **Live demo link + screenshots in the README** | soma | idea | Our equivalent is the seeded demo plus committed screenshots |
| **Maestro e2e flows per screen** (`verify-overview-trends`, `verify-chart-fidelity`, `verify-privacy`, …) | soma | idea | Way beyond MVP for us, but the *naming* is a good model: one flow per user-visible claim |
| **`share-image`, push rules, multiple outbound sinks** | soma | idea | Our single outbound sink is Apprise → Telegram. Their routing table is the grown-up version if that ever multiplies |
| **Desktop app via Tauri** | TrainingGeeks | idea, out of scope | Confirms the PWA decision: a desktop shell is a later, separate product |
| **Design system as a package** (`soma-style`) | soma | MIT code / idea | Our equivalent is `frontend/src/lib/chartDefaults.ts` + a palette file; the Okabe–Ito palette and one shared chart config are enough |
| **`scripts/shoot.mjs` — screenshot automation** | TrainingGeeks | idea | Feed `make seed` → screenshots, so README images are reproducible |

---

## What this list changes in the plan

1. **One new screen**: a `Sync` page over the `ingest_run` ledger (from soma's Sync Hub). Cheap, and it
   answers the question every ingestion bug raises.
2. **One new input to decide**: `S³` requires an RPE per session. If training includes strength work, this
   is the only honest way to count its load — and it is the only subjective input the system would ask for.
3. **Two new metrics in the layer**: 1-minute HR recovery (daytime-only, so it survives SC-05) and FFMI.
4. **One new DX guard**: `make seed` gets a drift test, so the demo cannot silently diverge from the schema.
5. **Nothing in the decision set changes.** The refusal list (ACWR, overtraining risk, opaque scores) is
   reinforced rather than challenged by seeing mature projects ship those exact features.
