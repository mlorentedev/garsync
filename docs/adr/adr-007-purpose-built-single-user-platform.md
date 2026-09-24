---
id: "adr-007-purpose-built-single-user-platform"
type: adr
status: accepted
owner: manu
date: "2026-09-24"
issue: ""
tags: [architecture, decision, scope, build-vs-adopt, garsync]
created: "2026-09-24"
---

# ADR-007: Purpose-Built Single-User Platform, No Health Backbone

## Status

Accepted — 2026-09-24, decided with the owner in the scope interview (SC-01 … SC-14, `docs/architecture/scope-interview.md`). Fixes the code-licence posture and the data-licence question (§6).

## Date

2026-09-24

## Context

GarSync is to grow from a Garmin dashboard into a personal health platform covering training, recovery, body composition and nutrition. That raises the classic question: adopt an existing open-source health/fitness backbone, or keep building.

The evidence (research brief 03) is that the field has already decomposed the problem into the same four pieces, and each piece is solved *at the edge* by a different project: device→app (Gadgetbridge, openScale), app→server (openScale-sync, with a declared unit contract), activity analytics (Endurain, intervals.icu, GoldenCheetah), plan/nutrition (wger). **No project owns the join across all four** — which is precisely the value of what is being designed here.

The most instructive case is Endurain: a self-hosted service built on essentially GarSync's stack (FastAPI + SQLAlchemy + Alembic + PostgreSQL + `python-garminconnect` + Apprise), which had synced Garmin activities, gear *and* body composition for years — and whose solo maintainer declared a temporary feature freeze in 2026-05 to repair module boundaries, background jobs and "the reliability of imports, syncs, and maintenance tasks". A mature project of the exact same shape had to stop shipping features to fix the same problems GarSync is about to meet.

The general health platforms (Medplum/HAPI FHIR, Open Health Stack, openEHR, Fasten) import multi-tenant clinical machinery whose interoperability payoff is zero for one patient and one consumer; Fasten OnPrem has already withdrawn provider import.

## Options Considered

1. **Adopt a backbone** (Endurain, wger, openScale+sync, Fasten/Medplum, Home Assistant). Rejected: none covers the four pillars; each imports operational weight, schema rigidity, or an abandonment horizon.
2. **Fork and extend an existing project.** Rejected: it inherits AGPL obligations, another project's roadmap, and a data model designed around its own vertical.
3. **Purpose-built single-user application that copies proven mechanics.** Chosen.
4. **Multi-user platform from the start.** Rejected here and in ADR-010 as a different product with a different legal position.

## Decision

1. GarSync remains a **purpose-built, single-user application**. No health backbone is adopted or wrapped.
2. What is copied is **mechanics, not code**: idempotent ingestion over natural keys, a declaration of canonical units with conversion at the receiver, a metric registry with FHIR-flavoured identity (no FHIR server), and real schema migrations before the schema grows.
3. **Code licence posture: stay permissive.** Copyleft neighbours (wger, openScale/GPL, Endurain/AGPL, Gadgetbridge/AGPL) are studied and, where useful, **run as separate processes** behind an interface — never vendored into this repository. The precision that matters, recorded so a future reader does not over-apply the concern: calling an unmodified AGPL program's API creates no derivative work of that program, so a separate container is not a licensing event; copying its source would be.
4. **The public surface, if any, is derived aggregates only** (volume, streaks, counts), from a separate deployment and database, with a note in the README that the values are public and correlatable. Weight, body composition, sleep, HRV and resting-HR series never appear there.
5. **Non-goals are declared now** so they stop being implied: multi-user tenancy, FHIR/openEHR interoperability, native mobile, social features, clinical claims, injury-risk models.
6. **Data licences are tracked separately from the code licence.** Open Food Facts is ODbL for the database, DbCL for its contents and CC-BY-SA for images. ODbL §4.5(c) exempts internal, non-public use from share-alike, so the private instance is unencumbered and keeps attribution in the UI regardless. But §4.4(c) makes a Derivative Database *Publicly Used* as soon as a Produced Work derived from it is published — so **the OFF-backed cache never feeds the public deployment**, and the public surface carries no nutrition-derived aggregate. A permissive code licence says nothing about a cached ODbL database.
7. **The confirmed v2 scope is training plus body composition, with nutrition deferred (SC-01/SC-03) and no language model anywhere in the product (SC-11).** The second of those supersedes [ADR-005](adr-005-ai-strategy.md) in intent: that ADR is live and proposes shipping health data to a hosted LLM endpoint, and this design does not.

## Consequences

### Positive

- No new platform dependency, no licence entanglement, and a data model shaped by this one person's questions rather than a vendor's tenant model.
- The portfolio value is the closed loop between training, recovery, body composition and diet — not a deployment of somebody else's product.

### Negative

- Idempotency, migrations and normalisation are now GarSync's own problem; Endurain's freeze is the warning that they must be solved *before* the schema grows, not after.
- No ecosystem, no plugins, no other users to share maintenance with.

### Neutral

- Endurain and intervals.icu remain useful as **specifications** (schema shapes, endpoint inventory, computed-metric semantics) even though they are not dependencies.

## References

- `docs/architecture/research/03-selfhosted-health-platforms.md`
- `docs/architecture/target-architecture-v2.md` §1, §9, §15 (**SC-04**, **SC-11**, **SC-12**)
- `docs/adr/adr-010-access-and-sharing-model.md`, `docs/adr/adr-009-data-substrate-and-migrations.md`
