---
id: "garsync-ticket-plan"
type: architecture
status: draft
created: "2026-09-24"
owner: manu
tags: [garsync, v2, planning, tickets]
depends_on: ["docs/architecture/target-architecture-v2.md", "docs/architecture/scope-interview.md"]
---

# Ticket plan — v2 MVP, for discussion

> **Not created yet, deliberately.** This is the scope of each ticket so it can be argued about before
> anything lands on the board. IDs follow the repo's `AREA-NNN` convention and the numbers are drawn from
> a live `gh issue list` at creation time, not from this document.
>
> **Gate rule applied below:** a ticket whose executable diff lands in the 50–300 LOC band, or which
> touches a public contract, needs an SDD spec (`dotf spec init <feature-id> --issue <N>`) in addition to
> the bitácora issue. Doc-only and config-only tickets are exempt. The **Gate** column says which.
>
> **MVP scope** is everything except the tickets explicitly marked *later* (§5).

---

## 0. Status — created 2026-09-24

The MVP set below was created on the bitácora as issues **#76–#98** (19 new tickets), after the scope
interview in `scope-interview.md` settled every open decision.

| Block | Issues |
|---|---|
| A — hygiene, SSOT, triage | `CHORE-004` #76 · `CHORE-005` #77 · `CI-002` #78 · `CHORE-006` #79 · `SEC-006` #80 · `DOC-001` #81 |
| B — substrate | `SUB-001` #82 · `SUB-002` #83 · `SUB-003` #84 · `SUB-004` #85 |
| C — metric layer | `MET-001` #86 · `MET-002` #87 · `MET-003` #88 · `MET-004` #89 |
| D — surface | `UI-001` #90 · `UI-002` #91 · `UI-003` #92 · `UI-004` #93 · `UI-005` #94 · `UI-006` #95 |
| E — deployment | `DEPLOY-002` #96 |
| F — the scale | `SCALE-001` #97 |
| G — DX | `DX-001` #98 |

Every ticket whose executable diff lands in the 50–300 LOC band still needs its spec
(`dotf spec init <ID> --issue <N>`) before a branch exists. **Nothing was closed automatically**: the
dispositions in §1 are proposals, and the absorbed issues (#37, #38, #40, #57, #59, #51) still need the
owner's word to be closed with a pointer.

---

## 1. Disposition of what is already open

Doing this first is what keeps the board honest — several of the eleven open issues are superseded by the
decisions in `scope-interview.md`, and two PRs are red and unreviewed.

| Existing | Proposed disposition |
|---|---|
| **#40 CHORE-001** hygiene quick-wins vs dotfiles/kubelab | **Absorbed.** Its content is split into CHORE-004/005/006 and CI-002 below, which carry the same intent with a decided scope |
| **#37 SYNC-001** scheduled sync + trigger endpoint + atomic pipeline | **Absorbed** into SUB-002 (ledger + atomic runs) and UI-005 (the weekly review delivery). The scheduler is in-process by ADR-008 |
| **#38 DEPLOY-001** deploy to NaN Cloud Apps | **Superseded in shape** by ADR-011: private instance on kubelab with two routes. Close and replace with DEPLOY-002, keeping the NaN findings as the recorded alternative |
| **#49 SEC-002** server-side session revocation | **Stays, and it is promoted**: ADR-010 makes revocation a prerequisite, not a follow-up. Fold its scope into the access work of DEPLOY-002 |
| **#50 SEC-003** login origin check + proxy-aware client IP | **Stays.** Small and independent of v2; the proxy-aware part belongs with the deployment (DEPLOY-002) |
| **#51 SEC-004** API-key-only dashboard access | **Decide and close.** ADR-010 answers it: the API-key surface becomes a single scoped read-only agent token, and the dashboard always requires a session |
| **#57 CHORE-002** unify Makefile targets | **Absorbed** into CI-002 (one gate surface, used by both CI and humans) |
| **#59 CI-001** harden workflow checkouts + PR-Agent guard | **Absorbed** into CI-002 |
| **#64 SEC-005** astro ≥ 7.1.0 paydown | **Closed 2026-09-25 with [ADR-014](../adr/adr-014-dependency-alert-policy.md).** Its “alerts list empty” criterion is re-scoped to *no alert whose vulnerable code is reachable in the deployed artifact*: the one library-level risk behind the critical alert (`sharp`) is patched in the lock (0.35.4), astro is build-time only here, and the framework-level fixes are the migration in CHORE-003 (#62) |
| **#62 CHORE-003** major upgrades (tailwind v4, TS v7) | **Stays, promoted to P1 (2026-09-25).** It absorbs the astro 7 half of SEC-005 — astro 7 needs the Tailwind v4 move (`@astrojs/tailwind` was replaced by `@tailwindcss/vite`, and v6 peers only astro 3–5), so the two tickets were one migration all along. It is now the only path to the framework-level fixes among the ten open alerts |
| **PR #66** astro 5 → 7.2.8 | **Closed 2026-09-25 as structurally unmergeable**: it carries one half of the migration and `npm ci` fails with ERESOLVE by construction |
| **PR #70** npm group, 2 updates | **Closed 2026-09-25** for the same reason: tailwindcss 3 → 4 alone leaves `@astrojs/tailwind@6` unsatisfiable. Folded into CHORE-003 (#62) |
| **PR #75** devalue 5.9.2 → 5.9.4 | **Merged** (#100). It was unreviewed when it landed — a notice that no review ran is not a review |

## 2. Block A — hygiene and SSOT (no spec required)

| ID | Title | In scope | Out of scope | Gate |
|---|---|---|---|---|
| **CHORE-004** | SSOT and drift | Add MIT `LICENSE` (the README already claims it); make `AGENTS.md` canonical and retire `GEMINI.md` (it points at `make test-backend`, which does not exist); mark ADR-005 `superseded` with a pointer to ADR-007/013; collapse `docs/lessons.md` + `docs/lessons/` into one SSOT with a generated index; fix the README's "scheduled incremental sync" claim (there is no scheduler); document the ADR 001–003 numbering gap | Rewriting ADRs 004–006 | doc-only |
| **CHORE-005** | Local guards | `.pre-commit-config.yaml` (gitleaks, ruff, ruff-format, mypy, trailing-whitespace, end-of-file-fixer), `.editorconfig`, `.gitleaks.toml`; align with the sibling repos' sets | CI changes (CI-002) | config-only |
| **CI-002** | One gate surface | `permissions:` and `concurrency:` on every workflow; `make check` becomes what CI runs so the two cannot diverge; **coverage measured and then ratcheted** (fail if it drops >2 points from the recorded baseline — no invented 80%); test markers (`unit`/`integration`/`e2e`) with `-m "not e2e"`; `docs-site` checked on PRs; **and the `frontend-check` target's fail-open repaired** — it printed `0 errors` and exited 0 with a failing `astro check` behind it | Publishing coverage badges before the number is real; and the two items split out below, both of which are bigger than a config line | config-only |
| **CHORE-006** | Dead dependencies | Drop `pandas`, `streamlit`, `plotly` — declared, zero references in `src/` or `tests/` | Touching anything else in `pyproject.toml` | none |
| **DOC-001** | Close the SEC-001 spec properly | Adversarial review of the merged-but-unarchived spec, then `dotf spec archive`; either way the archive gate becomes the demonstrated habit before SUB-001 | Re-opening SEC-001's decisions | doc + review |
| **SEC-006** | Resolve the astro contradiction | **Resolved 2026-09-25 → [ADR-014](../adr/adr-014-dependency-alert-policy.md).** The major-version ignore stays, *with its three required statements recorded in `dependabot.yml`* (why it cannot be taken, what is exposed meanwhile, what reopens it); the reachable library risk (`sharp`) is patched in the lock; the framework-level fixes move to CHORE-003 (#62), promoted to P1. #64 closed with that reasoning, #66 and #70 closed as structurally unmergeable | Any other dependency policy | none |

### Two items split out of CI-002 when it was implemented (2026-09-25)

The row above stopped claiming two things that are not config-only:

- **The review-attestation gate** is a 434-line script plus a 318-line `workflow_run` workflow in the
  sibling implementation, and `harness/review-attestation.json` is already read by
  `dotf pr triage-queue` — it is not a registry nothing reads, it is a registry missing its CI gate.
  Filed as **CI-003 (#106)**.
- **Frontend lint and format** needs `prettier` + `prettier-plugin-astro` (a new-dependency trigger) and
  reforms the whole of `frontend/src/`. Filed as **CHORE-007 (#105)**.

## 3. Block B — substrate (spec required)

| ID | Title | In scope | Out of scope | Est. exec LOC |
|---|---|---|---|---|
| **SUB-001** | Schema evolution + the v1→v2 migration | Alembic adopted; the baseline **stamps** the existing database; per-table migration per design §4.1 — `source` backfilled, HRV string kept alongside numeric columns born NULL, `sync_log` → `ingest_run` (legacy rows flagged), **activity timestamps normalised to UTC with `tz_offset_minutes`**, `goals` added; a test that upgrades a v1 fixture and asserts row counts *and* the TZ transformation; run against a copy of `data/garsync.db` first | Postgres-specific tuning; backfilling HRV numbers that were never stored | ~250 |
| **SUB-002** | Ledger, atomic runs, idempotent writes | `ingest_run` with cursors, one transaction per adapter run, `raw_payload` with asymmetric retention, `ON CONFLICT DO UPDATE` on natural keys, and **the test that re-running a window changes nothing**; the trailing re-derivation window (14 days) from SC-02 | A message broker — explicitly not, per ADR-008 | ~220 |
| **SUB-003** | Fetch by date, paginate, backfill | Activities fetched by date range with pagination (today they are fetched by `limit` only, so `--days` does not constrain them and nothing past 100 can be reached); a resumable, throttled backfill command that never blocks deployment; wellness backfill for the same window | Streams (SUB-004) | ~160 |
| **SUB-004** | Streams, lazily | `activity_streams` with a configured retention window; eager fetch for the recent window, on-demand fetch and persist for older activities; stream-dependent metrics computed **at ingest time** because the stream is not kept | Any metric that needs streams (that is MET-001+) | ~140 |

## 4. Block C — metric layer (spec required)

| ID | Title | In scope | Out of scope | Est. exec LOC |
|---|---|---|---|---|
| **MET-001** | Load and fitness | `hrTSS` from zone time with Garmin's `activityTrainingLoad` stored alongside as a cross-check; EWMA with configurable τ; CTL/ATL/TSB (42/7); ramp rate; monotony; strain; **1-minute HR recovery** (daytime-only signal, so it survives SC-05); `derived_daily` with a `data_quality` field; every value unit-tested against hand-computed fixtures | Anything needing streams (efficiency factor, decoupling) — those arrive with MET-001b once SUB-004 lands | ~260 |
| **MET-002** | Body composition | Weight EMA (α ≈ 0.1) + raw points retained; weight velocity over 28 days with a 42-day cross-check; body fat / fat mass / lean mass / FFMI trends; the trend classifier; algorithm-tagged composition rows with **nothing averaged**; the `goals` band | Local BIA maths; point values for fat % | ~170 |
| **MET-003** | The relationship, and one adjustment | The 28-day window joining accumulated load to body-composition change; lean-mass retention while volume rises; **one** rule-driven adjustment sentence with its inputs; `recommendation_log` recording the inputs and the later outcome; explicit "insufficient data, changing nothing" | Nutrition, calories, protein | ~160 |
| **MET-004** | Recovery, when it exists | RHR z-score and HRV CV computed from whatever overnight data exists; the coverage indicator that treats "no watch at night" as expected; **and the M5 check** (does the watch support Health Snapshot / does the pinned `garminconnect` expose it) to decide whether a morning ritual can feed this | Readiness as a hero; sleep debt | ~130 |

## 5. Block D — the surface (spec required)

| ID | Title | In scope | Out of scope | Est. exec LOC |
|---|---|---|---|---|
| **UI-001** | `Today` | One status line + four tiles with sparklines (load, weight vs band, composition, week) + the coverage line + the load-coloured mini-calendar reused from `Heatmap.astro` | New chart types, animations | ~250 |
| **UI-002** | `Body` | Weight trend with raw scatter and the goal band; composition trends with bands and the caveat line; **the relationship chart** (28-day load vs Δbody-composition) | Anything predictive | ~250 |
| **UI-003** | `Trends` | PMC with the ramp band; weekly load bars; monotony/strain; per-sport PMC; monthly volume; VO2max and race predictions as Garmin reports them; HR-vs-pace scatter | Peak curves and progression (need streams + a later ticket) | ~280 |
| **UI-004** | `Sync` + health | The `Sync` page over the ledger (run history, cursors, rows upserted, last error, last success per source) — **taken from soma's Sync Hub**; `/healthz` exposing database reachability and `last_sync_age_seconds`; the single ingest-health alarm routed through Apprise | Per-metric alerts; behaviour nudges | ~170 |
| **UI-005** | The weekly review | The Sunday review rendered as a page and pushed through Apprise → Telegram using the §11.1 template; the adjustment history from `recommendation_log` rendered as a list; the scheduler that triggers it | Daily briefs | ~200 |
| **UI-006** | A generated client | TypeScript client generated from OpenAPI with a drift check in CI; delete the hand-written interfaces in `frontend/src/lib/api.ts`; relative-URL default so the same build works on both routes | A codegen toolchain of its own | ~130 |

## 6. Block E — deployment (spec + one cross-repo ticket)

| ID | Title | In scope | Out of scope | Est. exec LOC |
|---|---|---|---|---|
| **DEPLOY-002** | garsync on kubelab, two routes | Service manifest in kubelab (`infra/k8s/base/services/`) + prod overlay; **two IngressRoutes** — tailnet with `vpn-whitelist` + Authelia `one_factor`, public with Authelia `two_factor`; SOPS secrets under the shared namespace; Postgres database + role with an agreed migration-ownership rule; backup coverage + **one exercised restore**; `Recreate` + single replica; footprint ceiling; `/healthz` and `/metrics` wired to the existing observability; **M6 verified on staging**; and the repo side: Dockerfile/entrypoint, non-root, no secrets in layers | A second deployment, a demo deployment, or a new host | ~220 |
| **SEC-002** (existing) | Session revocation | Folded in here as the prerequisite ADR-010 made it | Passkeys if they slip — TOTP first | ~120 |
| *(kubelab repo)* | Promote a third product | `toolkit deployment promote --app` accepts only `api｜web｜errors`. File **in kubelab**, not here: either generalise the allow-list or give a product its own Argo CD Application | Patching kubelab from this repo | cross-repo |

## 7. Block F — the scale (spec required, one ticket conditional)

| ID | Title | In scope | Out of scope | Est. exec LOC |
|---|---|---|---|---|
| **SCALE-001** | FitDays cloud adapter | **Record the M4 result first** (weigh-in with no phone present); the adapter behind the ADR-008 interface with SOPS credentials, a cursor, twice-daily cadence, **permanently retained raw payloads**, and reconciliation keyed `(profile, measured_at)` with both sources stored and the system of record named | A scraper in the core; local BIA maths | ~190 |
| **SCALE-002** | *Conditional on M4 failing* | Run an existing bridge that writes into Garmin (`jordanruthe/ble-scale-sync` or `garth-relay`) as a separate process; garsync reads Garmin unchanged. Written only if M4 shows weigh-ins are lost | Writing BLE protocol code | ~80 |

## 8. Block G — DX

| ID | Title | In scope | Out of scope | Est. exec LOC |
|---|---|---|---|---|
| **DX-001** | `make seed` with a drift guard | A deterministic populated database from existing fixtures, with no credentials — which is what finally lets CI and any reviewer run `make smoke`; **a drift test in the style of soma's `demo-drift`** so the seed cannot silently diverge from a migrated schema; screenshot generation from the seeded data for the README | A public demo deployment (SC-04 keeps it out) | ~160 |

## 9. Explicitly later — not in the MVP

| Item | Why it waits |
|---|---|
| Nutrition logging and the adaptive-intake loop | SC-01: deferred as a whole, no tables |
| **The app replaces the workbook**: plan editor (weekly template with type, intensity and step target), session logging with deviation notes, the protocol library, and the quarterly summary it already computes by hand | SC-18: the owner will integrate this in a future version; until then the spreadsheet stays his. The workbook is therefore the **requirements document** for that phase — it already defines the fields and the report — and the data model is designed to be able to hold it without building any of it now |
| LLM narration, MCP/agent surface | SC-11: none in v2 |
| Plan vs actual, annual training plan, RPE-driven load for strength (`S³`) | Needs a plan store and a subjective input; **the one decision this list raises** (see below) |
| Peak/pace-duration curves, progression, interval detection | Need streams, which SUB-004 introduces without consuming |
| A public read-only demo (static synthetic build) | SC-04: valid later, not now |
| Desktop shell (Tauri), share cards, push rules | Nice, not MVP |

## 10. Questions this plan raised, and how they were answered

1. **Does training include strength work?** **Yes, and it is roughly 40% of sessions** — measured in the
owner's own workbook (`Hipertrofia` 47, `Gym Fuerza` 20; per-quarter gym counts 31/16/14/13/32). Garmin's
HR-derived load under-measures strength, so the load series needs a strength path. The workbook also
settled **how** in principle: its protocol sheets encode intensity as `%RM` + `RIR` + `sets × reps`, which
is deterministic tonnage — better than an RPE. But the workbook is **not ingested in v2** (SC-18), so the
MVP uses Garmin's `activityTrainingLoad` for strength and **labels it a known under-estimate**, keeping the
zero-input property. No RPE is asked for.
2. **Is a `Sync` page worth a ticket?** **Yes** (SC-19), built as `UI-004` #93.

Two further scope changes came out of the workbook and are recorded in the register: a **canonical
`session_type` with the raw label preserved** is needed now, for Garmin's own `typeKey` zoo rather than for
the sheet (`SUB-003` #84), and the **`make seed` fixture takes its distribution from the workbook** so the
demo is realistic (`DX-001` #98).
