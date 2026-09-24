---
id: "garsync-review-v2-pass1"
type: review
status: complete
created: "2026-09-24"
owner: manu
tags: [garsync, v2, adversarial-review, architecture]
reviewer_model: "nan/mimo-v2.5"
author_model: "nan/deepseek-v4-flash"
verdict: "PASS-WITH-GAPS"
---

# Adversarial review — GarSync v2 target architecture, pass 1

**Material reviewed:** `docs/architecture/target-architecture-v2.md` and `docs/adr/adr-007..013`
(the seven ADRs), against the seven research briefs in `docs/architecture/research/`, the repository
source, and the kubelab platform manifests.

**Independence.** Reviewer: `nan/mimo-v2.5`. Author: `nan/deepseek-v4-flash` — a different model
family, and neither is Anthropic. Two notes on the pool itself:

- `harness/reviewer-pool.json` lists `agy/gemini-3.1-pro-high` as the provider-diverse arm, and that
  arm **is not launchable from this harness** — pi's model registry has no `agy` provider. A pool
  entry that can never run is the same defect class the pool's own provenance comment records for
  dotfiles (#1156: an arm that had never once run). Reported, not fixed here — it belongs to the
  harness, not to this repository.
- `nan/mimo-v2.5` is the pool's second fallback and was exercised for the first time in this
  repository by this review.

**Verdict as returned: PASS-WITH-GAPS.** Adjudicated verdict after this session's response to each
finding: **PASS-WITH-GAPS, all Blockers resolved in pass 2** (§Adjudication below states which
findings were accepted, and which were rejected or re-graded with the evidence that did it).

---

## Findings as returned

### B1 — No v1→v2 migration plan for the existing database (ACCEPTED)

Phase 0's exit criterion says "a migration test upgrades a v1 database to v2" and ADR-009 says the
v1→v2 baseline is generated from the existing schema — but **no document says what the migration
does**. The existing database has `activities`, `biometrics`, `sleep`, `sync_log`, `schema_version`;
v2 adds roughly ten tables, adds a `source` column and changes the unique key of `activities`, turns
HRV from a status string into numeric fields, replaces `sync_log` with `ingest_run`, and must
transform activity timestamps. An underspecified migration over years of history — on data that Garmin
will not necessarily serve again in full — is the highest-risk item in the plan.

**Fix applied:** new design §4.1, per-table migration table.

### B2 — ODbL share-alike obligation for Open Food Facts data (ACCEPTED AS MAJOR, NOT BLOCKER)

The review argued that caching Open Food Facts data locally could place the local database under ODbL
share-alike, and that a repository claiming MIT while carrying ODbL-obligated data is misleading.

**Adjudication — the severity was wrong, and reading the licence text changed the fix.** ODbL §4.5(c)
states that *"Use of a Derivative Database internally within an organisation is not to the public and
therefore does not fall under the requirements of Section 4.4"*, and §4.4(a) attaches share-alike to a
Derivative Database that is *Publicly Used*. A private, single-owner instance is therefore **not**
obligated. The finding becomes real at a different point the review did not name precisely: §4.4(c)
makes a Derivative Database "Publicly Used" *if a Produced Work created from it is Publicly Used* —
which is exactly the public demo instance that ADR-007 §4 and ADR-011 §7 propose. It was also wrong to
frame this against the repository's code licence: the database obligation is orthogonal to MIT.

**Fix applied:** ADR-007 gains a data-licence decision: the OFF-backed cache is private-only and must
never feed the public deployment; attribution stays in the UI regardless; the public demo carries no
nutrition-derived aggregate. Recorded in design §8 and §9.

### M1 — Timezone semantics identified but not decided (ACCEPTED)

`client.py` stores activities from naive `startTimeLocal` and sleep from a UTC epoch
(`client.py:87` vs `:108`), and the design says only that "timezone semantics fixed" is a phase-0 exit
criterion. "Fixed" is not a decision, and the derived layer (CTL/ATL windows, day boundaries, the
07:00 digest) depends entirely on it.

**Fix applied:** decided in ADR-008 — canonical timestamps in UTC, the source's local string retained
in `raw_data`, an explicit `tz_offset_minutes` column, and daily rollups keyed to a configured
`GARSYNC_TZ` local calendar day. Design §15 records it as settled rather than open (D9).

### M2 — Stream retention window vs metrics that need long stream history (ACCEPTED)

Efficiency factor, decoupling, interval detection and duration curves need per-second streams, but
streams are retained for 90 days while "derived metrics persist forever". Whether those metrics are
computed at ingest time (before the stream expires) or recomputed later from nothing was unspecified.

**Fix applied:** ADR-008 and ADR-013 state that stream-dependent metrics are **computed at ingest time
and persisted**, that a formula change requires a recompute from the retained `raw_payload`, and that
a stream that was never retained is not recoverable — so the retention window is a *scope* choice for
which historical metrics can be recomputed, not merely a disk choice.

### M3 — `D8` appears as an open decision while ADR-007 already decides it (ACCEPTED)

**Fix applied:** the licence posture is a decided item in ADR-007 and is no longer listed as open in
design §15.

### M4 — Digest content not specified (ACCEPTED)

The daily brief is the primary delivery surface and the design gave only format rules.

**Fix applied:** design §11 gained a §11.1 digest template: hero line, up to three named contributors
with deltas, coverage, one deep link, and explicit fallback text for a day with no new data.

### M5 — AGPL implications for the nutrition pillar (PARTIALLY REJECTED)

The review asserted that communication between a separate AGPL container and garsync could obligate
garsync's code, and that "for a single-operator deployment where both containers are on the same
machine, the AGPL network copyleft arguably applies".

**Rejected on the substance.** AGPL §13 attaches to a *modified version* of the program being
interacted with over a network, and to conveying it; a separate program calling that program's API
creates no derivative work of it, on the same reasoning that makes HTTP clients of AGPL services
unencumbered. Running an unmodified AGPL container and calling it does not relicense the caller. The
review's own Minor m1 half-corrects this. What *is* true, and was already in ADR-007, is the rule that
matters: **no copyleft source is vendored into this repository.**

**Fix applied:** ADR-007 gains one precise sentence rather than the paragraph of hedging the review
implied, so a future reader does not over-apply the concern.

### M6 — Two-adapter disagreement about the same day (ACCEPTED)

**Fix applied:** ADR-012 now names the reconciliation key and the priority rule: both rows are stored,
each tagged by source and algorithm, and the declared system of record selects what is displayed.

### M7 — "Coverage is a real number" has no threshold (ACCEPTED, with a different fix than proposed)

The review proposed either recording the number or setting a floor. Both are arbitrary at this point.

**Fix applied:** a **ratchet**: phase 0 measures and records the baseline in CI, and CI fails if
coverage *falls* by more than two points from that baseline. No invented 80% target; the number becomes
visible and monotone, which is what makes it a constraint rather than a claim (and it retires the
PRD's unmeasured ">80%" at the same time).

### Minor findings

| # | Finding | Disposition |
|---|---|---|
| m1 | AGPL network copyleft nuance | Accepted, folded into M5's fix |
| m2 | FitDays cloud credential lifecycle unspecified | Accepted — ADR-012 now states re-validation per run and that auth failure routes through the staleness alert |
| m3 | "Zero manual steps" ambiguous | Accepted — phase 4 gate now reads "no manual CSV import or data entry after the initial M1 scan" |
| m4 | VPS resource envelope unspecified | Accepted — ADR-011 now carries a ceiling (~128MiB request / 256MiB limit, ≤0.2 CPU, ≤5GiB disk with the retention caps in ADR-008) |
| m5 | ADR-005 (AI strategy) not referenced | Accepted — ADR-005 is a live, accepted ADR proposing a cloud-LLM chat endpoint, and it **conflicts with ADR-013's privacy position**. ADR-013 and design §15 D7 now reference it explicitly: the v2 agent surface supersedes ADR-005's design, and no raw health series leaves the cluster |

### What the review could not verify (as returned)

Dynamic GitHub state (issue and PR counts, the CodeRabbit skip notices); kubelab's forward-auth
fail-closed behaviour; Hetzner disk encryption at rest; passkeys from an installed PWA; the pinned
`garminconnect` signature for `add_body_composition`; the scale's BLE family. Each is either named as
an M-series measurement in design §12 or listed as unverified in §16.

---

## Adjudication summary

| Finding | Returned severity | Adjudicated | Where fixed |
|---|---|---|---|
| B1 migration of existing data | Blocker | Blocker, accepted | design §4.1 |
| B2 ODbL share-alike | Blocker | **Major** — §4.5(c) exempts private use; live only at the public demo (§4.4(c)) | ADR-007, design §8/§9 |
| M1 timezone semantics | Major | Major, accepted | ADR-008, design §15 |
| M2 stream retention scope | Major | Major, accepted | ADR-008, ADR-013 |
| M3 D8 duplication | Major | Major, accepted | design §15 |
| M4 digest content | Major | Major, accepted | design §11.1 |
| M5 AGPL for the nutrition pillar | Major | **Rejected** as stated; the actionable rule was already in ADR-007 | ADR-007 |
| M6 adapter reconciliation | Major | Major, accepted | ADR-012 |
| M7 coverage threshold | Major | Major, accepted with a ratchet instead of a floor | design §13 |
| m1–m5 | Minor | All accepted | as listed above |

## Findings this review did not catch, recorded by the author

- **The decision-status legend contradicted the ADRs.** Design §0 defined `[D]` as "Decided — an ADR
  records it" while every ADR in this pass is `status: proposed`. A reader would have taken seven
  proposals for accepted decisions. Fixed in §0, and disclosed here rather than quietly repaired.
- **The PRD's own acceptance criteria are not re-examined by any ADR.** `prd-v1.md` claims ">80%
  coverage", "Docker build <60s", "API response <200ms" and "LCP <2s". Only coverage is touched by
  this pass (M7); the other three remain unmeasured claims in a document that reads as a contract.
- **`data/garsync.db` exists in the working tree** while `data/` is gitignored — so the migration path
  in B1 is not a theoretical concern; there is a real database with real history on disk today.

## Evidence

- ODbL 1.0 text, §4.4 and §4.5(c): `https://opendatacommons.org/licenses/odbl/odbl-10.txt` (accessed 2026-09-24)
- Open Food Facts licence guidance: `https://openfoodfacts.github.io/openfoodfacts-server/api/tutorials/license-be-on-the-legal-side/` (accessed 2026-09-24)
- Reviewer run: `nan/mimo-v2.5`, single-child run `245dbc36`, 2026-09-24
