---
id: "adr-013-analytics-and-recommendation-discipline"
type: adr
status: accepted
owner: manu
date: "2026-09-24"
issue: ""
tags: [architecture, decision, analytics, metrics, readiness, coaching, uncertainty, garsync]
created: "2026-09-24"
depends_on: [adr-008-ingestion-ledger-and-adapters, adr-009-data-substrate-and-migrations]
---

# ADR-013: A Deterministic, Auditable Metric Layer and a Bounded Recommendation Layer

## Status

Accepted — 2026-09-24, with two scope consequences recorded in the decision: recovery is **conditional** (SC-05) and the MVP hero is the load↔body-response relationship (SC-06). The open product choice that remains is goal mode (cut/maintain/bulk), to be settled when the `Body` screen is designed.

## Date

2026-09-24

## Context

The point of v2 is to *adjust* training, recovery and diet rather than merely chart them, so the metric layer is the product. Two temptations sit in front of that goal and both are documented failures.

**Temptation one: a composite black-box score.** A 0–100 readiness number is familiar and looks like a product. It is also unfalsifiable to its user, and the vendor scores it would imitate are themselves opaque. The research's position is that a readiness score is acceptable for familiarity **only if its contributors are visible and separately checkable**.

**Temptation two: a model.** The literature on exactly the metrics this domain reaches for first — ACWR as a decision input, machine-learned injury-risk scores — is a record of confident numbers that do not survive external validation (30/30 externally-unvalidated, per the brief). Meanwhile the interventions with the best evidence are boring: progressive overload, consistent volume, sane taper parameters, sleep regularity.

There is also a set of gaps in the current repository that constrain what is computable at all, verified by reading it on 2026-09-24:

- **No per-second streams.** `activity_streams` does not exist; only activity summaries are stored. Decoupling, efficiency factor, pace/power-duration curves, interval detection and any W′-style work are therefore off the table until it lands — and the library already ships the parser for the detail samples.
- **HRV is stored as a status string** (`biometrics.hrv_balance` holds `baselineStatus`), so no numeric series, no trend, no coefficient of variation and no personal baseline exist — although the numbers are present in the same response.
- **Garmin's own derived values are discarded** — `activityTrainingLoad`, aerobic/anaerobic training effect and the readiness factor decomposition are in payloads the client already models, and are thrown away into a `raw_data` column while nothing surfaces them.
- **Sleep is stored but under-analysed**, and there is **no body-composition series at all**, because the scale does not feed the system yet.

## Options Considered

1. **Chart what Garmin gives and add a recommendation later.** Rejected: it is what v1 does, and it leaves the product without a reason to exist beyond Garmin Connect.
2. **A deterministic metric layer plus a small, explicitly uncertain recommendation layer.** Chosen.
3. **A vendor-style composite readiness score only.** Rejected as the sole output: familiar but unfalsifiable. Retained as one presentation of a decomposed score.
4. **A trained model over personal history.** Rejected: no validation path exists on one person's data, so its errors would be undetectable.
5. **A general-purpose, multi-athlete coaching engine.** Rejected: it needs a validation population the owner does not have; a single-user system can be honest about being tuned to one person (and should say so).

## Decision

1. **All derived metrics are deterministic, pure functions over stored inputs**, recomputed rather than hand-edited, and unit-tested against hand-computed fixtures. Every value is reproducible from the database alone.
2. **The metric layer ships in this order**: (i) load and fitness — `hrTSS` from zone time with Garmin's `activityTrainingLoad` shown alongside as a cross-check, CTL/ATL/TSB with λ = 2/(N+1) and 42/7 windows, ramp rate as 7-day Δ as % of CTL, monotony and strain; (ii) recovery — RHR 7-day mean and deviation, HRV as ln-rMSSD trend with a weekly coefficient of variation and a personal baseline z, sleep debt against a **stated** need, sleep regularity index; (iii) streams, then efficiency factor, decoupling and interval detection — **computed at ingest time and persisted, since the streams themselves are retained for a bounded window**; (iv) the recommendation layer.
3. **Readiness is transparent**: a z-score sum over three to five named inputs, each displayed with its own delta against a personal baseline, plus a per-day `data_quality` indicator ("12 of 14 days present"). A 0–100 presentation is permitted; an opaque one is not.
4. **Refusals are part of the decision.** Not built: ACWR as a decision input (reported descriptively at most), injury-risk scores, any trained model, DFA α1 thresholds, orthostatic testing (no controlled protocol or hardware), and population baselines where a personal one exists.
5. **Recommendation layer is bounded**: expressed as ranges, gated on concurrence of named signals, capped in magnitude, and **logged in `recommendation_log` with its inputs and its later outcome**. If the outcome is never recorded, the confidence claim is unfalsifiable — so the table is part of the feature, not a follow-up.
6. **The system must be able to say "insufficient data, changing nothing"**, and that state is a first-class output rather than an error.
7. **Personal baselines only.** Where a published population threshold is used, it is labelled as such.
8. **Whose load number is canonical is a stated choice, not an accident**: computed `hrTSS` is canonical for the series, Garmin's number is displayed as a cross-check, and divergence between them is logged rather than silently reconciled.
9. **The recovery half is conditional, not a pillar (SC-05).** The owner rarely sleeps with the watch, so sleep stages, overnight HRV, resting HR, overnight Body Battery recharge and therefore Garmin Training Readiness are **absent on most days**. These metrics are stored when they exist and contribute when present; they are never the protagonist, the application does not compete with a readiness score it usually cannot compute, and "did not sleep with the watch" is an **expected** state in the coverage indicator rather than a missing-data error. Sleep debt and the sleep regularity index leave the MVP.
10. **The MVP hero is the relationship, not a status (SC-06)**: how weight, body fat and lean mass respond to accumulated training load — a 28-day trend of body composition against accumulated load, with lean-mass retention while volume rises. This is computable precisely because the owner trains and weighs daily (SC-13), and it is the join no vendor performs. `goals` (ADR-009) is what makes it readable.
11. **No language model participates in v2 (SC-11).** The weekly review is a deterministic template over computed values, with one rule-driven adjustment sentence, every phrase traceable to its inputs. An LLM would add prose rather than insight to an arithmetic review, the local option lives on an on-demand homelab node (ADR-028), and the hosted option contradicts the private-surface decision — so this ADR supersedes [ADR-005](adr-005-ai-strategy.md) in intent. If a model ever enters, it **narrates and never prescribes**, over pre-aggregated windows only.

## Consequences

### Positive

- Every number can be explained to its user, which is both the honest posture and the actual differentiator against vendor dashboards.
- Recomputation from stored inputs means a formula change is a replay, not a data loss.
- The refusal list prevents the most expensive category of work in this domain: models that cannot be validated here.

### Negative

- A transparent readiness score will **disagree with the watch**, and for a single operator that disagreement is a support burden. It must therefore be presented alongside Garmin's rather than in place of it, at least initially.
- Recommendation logging adds a table, an obligation to record outcomes, and the discipline to review them.

### Neutral

- The metric layer is deliberately uninteresting engineering: arithmetic, fixtures and reproducibility. That is the point, and it is also what makes the project presentable as an engineering artifact rather than a chart gallery.

## References

- `docs/architecture/research/04-training-analytics-and-coaching.md`, `research/05-nutrition-and-body-composition.md`
- `docs/architecture/target-architecture-v2.md` §6, §8, §15 (**SC-05**, **SC-06**, **SC-11**, **SC-13**)
- `docs/adr/adr-008-ingestion-ledger-and-adapters.md`, `docs/adr/adr-009-data-substrate-and-migrations.md`
- `docs/adr/adr-005-ai-strategy.md` — the accepted AI-strategy ADR proposes a cloud-LLM chat endpoint (`POST /api/ai/chat`). This ADR supersedes it in intent: the agent surface is read-only, bounded to pre-aggregated windows, and, if it ships, it runs **locally**. No raw health series leaves the cluster.
