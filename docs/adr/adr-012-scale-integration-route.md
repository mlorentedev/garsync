---
id: "adr-012-scale-integration-route"
type: adr
status: accepted
owner: manu
date: "2026-09-24"
issue: ""
tags: [architecture, decision, scale, ble, body-composition, vendor-risk, garsync]
created: "2026-09-24"
depends_on: [adr-007-purpose-built-single-user-platform, adr-008-ingestion-ledger-and-adapters]
---

# ADR-012: Scale Integration — Identify First, Capture Locally, Poll the Cloud Only as Backfill

## Status

Accepted — 2026-09-24, **conditional on measurement M4** (a weigh-in with the phone in another room appears in the app with its original timestamp). M4 failing does not void the principles below; it promotes BLE from remedy to primary, and pass 1's route analysis is retained for exactly that case.

## Date

2026-09-24

## Context

The owner's bathroom scale is currently readable only through the FitDays mobile app. The research established that this framing is misleading in a way that changes the design: **FitDays is an application (Guangdong ICOMON), not a scale family**, and it fronts at least three physically different BLE families. Two of those families broadcast or serve their measurement to any listening device with **no account binding at the link layer**. The constraint is therefore a property of the vendor's cloud and app, not of the hardware.

That matters because the four available routes have genuinely different failure modes:

- **Local BLE capture** — no vendor in the loop, real-time on stabilisation, and for one family the composite frame already contains fat/muscle/bone/water. Requires a host in range.
- **Cloud polling** — the richest payload (13 vendor-computed parameters plus impedance, ~400 days of history) and the most fragile: an undocumented, rotating, single-maintainer surface, bounded by whether the phone was present and the app was open. A weigh-in that never reaches the cloud is **invisible to a poller, and the failure is silent**.
- **App-mediated export** — manual forever, stable.
- **Replacing the scale** — the honest escape hatch, and the cheapest route to the best-supported protocols.

Two further facts drive the decision. First, the maintained BLE scale daemon is **GPL-3.0**; this repository is permissive (ADR-007) and intends to stay so. Second, the two computational paths disagree materially: a measured case produced **39.7%** body fat from one local formula against **29.1%** from another on the same reading (103.3 kg / 518 Ω / 193 cm / male 55). Merging those into one field, or averaging them, would produce a series that is neither the app's number nor the formula's.

## Options Considered

1. **Reverse-engineer the FitDays cloud inside `src/garsync/` and make it the only path.** Rejected: it makes a private rotating endpoint the system of record for a health series, and it puts a scraper in the core of a portfolio repository.
2. **Vendor the GPL BLE daemon into this repository.** Rejected: it imports copyleft into a permissively licensed project for a capability that is available at a process boundary.
3. **Local BLE capture as a separate process, cloud polling for backfill/reconciliation.** Chosen.
4. **Rely on the app's CSV/Health-app export.** Rejected as primary; retained as a documented emergency fallback.
5. **Replace the scale.** Held in reserve: it becomes the recommendation if M4 fails **and** no local capture is viable — ADR-007's ranking treats buying a well-supported protocol as a legitimate answer rather than a defeat.

## Decision

1. **Route: cloud-first (SC-09).** The FitDays cloud poller is the **primary** source and BLE capture leaves the MVP. This inverts pass 1, and the argument is simplification, not preference: the poller is required anyway as the only source of the ~400 days of history (SC-08), the owner reports that the scale already syncs and uploads through the app, and making it primary removes a process, all hardware, a GPL process boundary and roughly a week of work. The BLE identification scan that pass 1 put first is therefore **cancelled as a task** — it existed only to choose a BLE route.
2. **M4 is the condition, and it is a behaviour test, not a capability test.** "It already syncs" describes what happens when the phone is present. M4 asks what happens when it is not, because the failure mode is silent: a weigh-in that never uploads is indistinguishable from not weighing. While M4 is unrun, the design keeps the cloud primary but treats the possibility of lost weigh-ins as open.
3. **If M4 fails, the first remedy is an existing bridge, not new code.** `jordanruthe/ble-scale-sync` reads 25+ BLE smart scales and exports to **Garmin Connect** (among MQTT, InfluxDB, webhooks and Telegram), so the fix is to run it near the scale and let garsync read Garmin — which it already does. That costs no BLE protocol work and no new adapter. Pass 1's alternative remains the second remedy: a local capture process (its own container or a small host near the scale) emitting over webhook or MQTT, which keeps copyleft at a process boundary (ADR-007) and keeps garsync a receiver with no BLE dependency in its core. `cyberfossa/garth-relay` is the same write-into-Garmin path packaged as a service, if the chosen bridge is not maintained.
4. **The cloud poller runs as an ordinary adapter** (ADR-008) with SOPS-stored credentials, a cursor and a ledger row, at its own cadence (twice daily, morning and evening). Its raw payloads are retained **permanently** (SC-08), unlike Garmin's, because the endpoint is reverse-engineered and may disappear.
4. **One declared system of record per body-composition series.** The vendor's numbers are the recommendation (they are what the app shows and what any clinician-facing export will contain), with locally derived values stored in separate `algorithm`-tagged rows. **Nothing is averaged and nothing is merged.**
5. **Raw inputs are retained** (weight, impedance, timestamp, source) so every derived value can be recomputed when a coefficient changes (ADR-009 §5).
6. **Local BIA maths is a separate, later task**, and it is only worth attempting with a validated impedance reading and a stated equation plus fallback and an accepted input range.
7. **Presentation rules are part of the decision, not a UI detail**: weight and its trend are point values; body fat, fat mass, lean mass, visceral fat, "metabolic age" and scale-derived BMR are **trends with bands** behind a one-line caveat, defaulting to a 7-day median.
8. **Garmin is not the transport.** If the scale's data is mirrored into Garmin for portability, that is a one-way convenience copy; it never becomes the source garsync reads to close the loop.
9. **Reconciliation rule.** The key is `(profile, measured_at)`. Both sources' readings are stored, each tagged with its source and algorithm; the declared system of record selects what is *displayed*, and a disagreement between sources becomes a data-quality flag rather than a silent resolution. Nothing is averaged, and no row is overwritten by a different algorithm's opinion.
10. **Credential lifecycle for the cloud route.** Credentials live in SOPS and the client's password-equivalent digest is treated as a secret. Authentication is re-validated on every run, and an auth failure raises through the same staleness alert path as a missing weigh-in — so a broken poller is loud instead of looking like a fortnight of not stepping on the scale.

## Consequences

### Positive

- The vendor's app can change, break or disappear without the body-composition series stopping.
- The licence boundary is architectural rather than a licence-compatibility argument.
- Real-time weigh-ins become possible without a phone in the room, which is also the difference between "the scale said" and "the app uploaded".

### Negative

- One more process to deploy and monitor, and it lives where the scale lives rather than where the cluster lives.
- If the identified family needs connect-and-hold, the capture process must handle the case where the vendor app holds the link first.
- The cloud route's silent-failure mode needs an explicit gap detector; without it, a missing weigh-in looks like a day the owner did not weigh.

### Neutral

- The BLE route analysis stays in the ADR after the decision so a future reader can see what the remedy is, and what would have to change for it to be needed.

## References

- `docs/architecture/research/01-smart-scale-fitdays.md`, `research/05-nutrition-and-body-composition.md`
- `docs/architecture/target-architecture-v2.md` §7, §12 (**M4**, **M5**), §15 (**SC-09**)
- `docs/adr/adr-007-purpose-built-single-user-platform.md` (licence posture), `docs/adr/adr-008-ingestion-ledger-and-adapters.md` (adapter contract)
