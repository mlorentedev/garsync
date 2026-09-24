---
id: "adr-011-deployment-topology"
type: adr
status: accepted
owner: manu
date: "2026-09-24"
issue: ""
tags: [architecture, decision, deployment, kubelab, kubernetes, hosting, garsync]
created: "2026-09-24"
depends_on: [adr-009-data-substrate-and-migrations, adr-010-access-and-sharing-model]
---

# ADR-011: Deployment Topology — Private Instance on kubelab, Demo on NaN

## Status

Accepted — 2026-09-24, with two prerequisites that void it if they fail (item 8), and one measurement (M6) that decides which route is the daily one.

## Date

2026-09-24

## Context

Two hosting options were in play before this session, and the research re-framed them rather than choosing between them.

**NaN Cloud Apps (Basic Space)** was the original plan (DEPLOY-001, #38): a Dockerfile deploy, free with the owner's inference membership, public HTTPS subdomain. Its measured constraints are that apps are world-reachable with **no platform authentication of any kind**, env vars are the only secret mechanism with no masking, persistence is a PVC with **no documented backup story**, and there is no platform cron (so scheduling must be in-process). A SQLite-on-a-PVC app with a single replica is workable; anything requiring an edge, a VPN, backups or observability is not.

**kubelab** — the owner's own platform — already has the pieces this design calls for: K3s prod on the Hetzner VPS and staging on a homelab node, Argo CD app-of-apps, Traefik with an existing `authelia` forward-auth middleware plus `secure-headers`, `rate-limit` and `crowdsec-bouncer`, SOPS+age secrets with a namespace convention, a **shared PostgreSQL service**, Loki+Vector→Grafana, an **Apprise** notification service that is exactly the transport for a daily digest, per-PVC daily backups in prod, and a quota watcher guarding the VPS.

Reading kubelab's repository in this session surfaced three concrete integration gaps rather than abstractions: `toolkit deployment promote --app` accepts only `api|web|errors`, so promoting a third product needs either that allow-list generalised or a per-product Argo CD Application; ownership of an app's own schema migrations needs settling against the platform's ADR-051 mandate; and the PVC backup path covers prod only.

The honest conclusion is that the two hosts are not competing for one product — they are two products. The private instance (weight, body composition, sleep, HRV, nutrition) belongs where the controls exist. A **seeded public demo** (aggregate counts and streaks, synthetic data) is a portfolio artifact with no personal data in it, and Basic Space is a good fit for exactly that.

## Options Considered

1. **NaN Basic Space only.** Cheapest path to a URL, and correct for a demo. Rejected as the home for real health data: no platform auth, no backup story, no edge, no observability, no notification fabric — every compensating control would have to be rebuilt inside one container.
2. **kubelab prod only.** Chosen for the private instance: every required control already exists and is maintained by an owner who already runs it.
3. **kubelab staging for the private instance.** Rejected: staging is disposable by design and the homelab node is powered on demand.
4. **Both, for two distinct products.** Chosen: private instance on kubelab, seeded aggregate demo on NaN.
5. **A new managed host (Fly.io, a second VPS).** Rejected: adds a third environment for one user, with no control the existing two do not already provide.

## Decision

1. **The private instance is deployed to kubelab prod** (Hetzner VPS K3s) as a service under `infra/k8s/base/services/` with a prod overlay, `Recreate` strategy and a single replica, following the platform's existing stateful-service precedent.
2. **Routing and auth**: an IngressRoute carrying `secure-headers`, `rate-limit`, `crowdsec-bouncer` and the existing `authelia` forward-auth middleware — the edge boundary of ADR-010 — with the application's own session as the second boundary, and a VPN-restricted break-glass route that survives GitOps reconciliation.
3. **State**: PostgreSQL from the shared service for production (ADR-009), with local PVC state limited to what cannot live in the database. Whatever remains on a PVC must be covered by the platform's prod backup path, and a **restore is exercised once** before the instance is considered live.
4. **Secrets** follow the platform's SOPS path under the shared-namespace convention, never env vars in a dashboard.
5. **Delivery**: images built once and promoted by immutable tag/digest, per the platform's existing doctrine. The `promote` allow-list gap is raised **in kubelab** as platform work, not patched from here.
6. **Observability and alerting**: structured logs to Loki; `/healthz` exposing database reachability and `last_sync_age_seconds`; **one** alert at >36h of staleness routed through the existing Apprise service, which also carries the 07:00 brief and the Sunday review.
7. **Reachability is two routes over one deployment (SC-04), not a public-or-private choice.** A tailnet route carries `vpn-whitelist` and Authelia at `one_factor` with a long session, so opening the app from the phone needs no prompt and nothing is reachable from the internet; a public route sits behind Authelia at `two_factor` for devices that cannot join the mesh. `trusted_cidrs` already contains `100.64.0.0/10` (`infra/config/values/common.yaml:53-57`), so the one-factor-for-tailnet policy is a configuration line rather than new machinery. **No public data surface and no demo deployment exist in v2** — a static synthetic demo remains a separate, later decision (SC-04), and `make seed` is a phase-0 deliverable for CI and screenshots, not a public artefact.
8. **Prerequisites before this decision is executable** (either failing voids it): (a) kubelab's Traefik `forwardAuth` fails **closed**, verified empirically on staging by stopping Authelia and recording the response; (b) the shared Postgres has an agreed migration-ownership rule for an app-owned schema. Both are shared with **M6**, which additionally checks that a phone on 4G reaches a tailnet-resolved name *through the tunnel* (source `100.64.x.x`) rather than over the public internet, where the whitelist would deny it. Until M6 passes, route B — public name, login, 2FA, 30-day session — is the daily path and route A is the optimisation.
9. **Footprint ceiling**: request 128MiB RAM / 0.1 CPU, limit 256MiB RAM / 0.5 CPU, single replica, disk bounded by ADR-008's retention caps to ≤5GiB. Exceeding the ceiling is a signal to revisit the retention windows, not to ask the VPS for more.

## Consequences

### Positive

- Lifetime cost is unchanged: the private instance rides infrastructure the owner already pays for and already monitors.
- Backup, restore, secrets, notifications, logs and SSO are inherited rather than rebuilt — the four things a single-operator health app silently fails at.
- The two-boundary auth model of ADR-010 becomes the deployed reality rather than a design intent.

### Negative

- A public hostname on the VPS becomes the address of the owner's health data. This is why ADR-010 carries two boundaries, no share routes, and a documented break-glass path.
- GarSync's deployment now depends on kubelab's promotion tooling accepting a third product, and on the VPS's resource envelope.
- Deploying to a platform whose manifests live in another repository means every change to garsync's Kubernetes shape is a cross-repo pull request.

### Neutral

- Moving later from kubelab to NaN (or the reverse) is a packaging exercise, not an architectural one, because ingestion, storage and auth are all inside the application.

## References

- `docs/architecture/research/06-access-privacy-and-sharing.md`, `research/07-ux-dx-packaging-and-delivery.md`
- `docs/architecture/target-architecture-v2.md` §10, §15 (**SC-04**) · measurements **M6**
- `docs/adr/adr-010-access-and-sharing-model.md`, `docs/adr/adr-009-data-substrate-and-migrations.md`
- Cross-repo: kubelab ADR-024 (PVC backups, prod only), ADR-046/056 (promotion, build-once), ADR-051 (shared Postgres + migrations), ADR-053 (product repos), ADR-061 (stateful placement); issue DEPLOY-001 (#38) is superseded in scope by this ADR
- Vault: `00_meta/patterns/pattern-nan-cloud-apps.md`
