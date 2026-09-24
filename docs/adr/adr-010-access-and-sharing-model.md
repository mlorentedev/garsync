---
id: "adr-010-access-and-sharing-model"
type: adr
status: accepted
owner: manu
date: "2026-09-24"
issue: ""
tags: [architecture, decision, auth, privacy, sharing, gdpr, garsync]
created: "2026-09-24"
depends_on: [adr-006-single-user-session-gate, adr-007-purpose-built-single-user-platform]
---

# ADR-010: Two Authorization Boundaries, Passkey-First Sessions, and Export-Only Sharing

## Status

Accepted — 2026-09-24. Amends [ADR-006](adr-006-single-user-session-gate.md); supersedes it only where stated.

## Date

2026-09-24

## Context

ADR-006 shipped an application password with a stateless HMAC session token, explicitly accepting three limitations: no per-session revocation (SEC-002, #49), no proxy-aware origin/IP handling (SEC-003, #50), and an unresolved question about API-key-only dashboard access (SEC-004, #51).

That was proportionate for a Garmin dashboard. The data this application is about to hold is different: weight, body composition, sleep, HRV, resting heart rate, nutrition and (soon) training load are ***Article 9 special-category health data***. The threat model changes in three ways: the value of the corpus rises, the number of endpoints rises (a PWA, a digest pipeline, and an agent token), and the deployment target may be a public hostname whose platform provides no authentication of its own.

The auth research also found that the strongest available posture is not a single better gate but **two independent ones**, because the edge middleware class has had bypass advisories and edge policies (`bypass`, network criteria) are configuration-sensitive — and because the in-app gate must work in a deployment that has no edge at all.

Finally, the question "should anyone else be able to see this?" has a cheap honest answer and an expensive dangerous one: export on demand, versus a public share route onto special-category data.

## Options Considered

1. **Keep ADR-006 as-is and add TOTP later.** Rejected: the revocation gap and the redirect-based XHR failure mode are both wrong for a PWA carrying health data.
2. **Edge-only (Authelia forward auth), removing the application gate.** Rejected: it couples access to an IdP this application does not run, and it does not exist on every deployment target (ADR-011 keeps a NaN-hosted demo in scope).
3. **Application-only (no edge).** Rejected as the *sole* design, not as a component: it is what the NaN-hosted demo would have, and it makes one middleware bypass equal a full data exposure.
4. **Both boundaries, passkey-first, export-only sharing.** Chosen.
5. **Multi-user with tenancy.** Rejected here; conditions to reopen are stated below.

## Decision

1. **Two independent authorization boundaries.** At the edge where the deployment supports it (Authelia forward-auth, second factor on external requests), and **always** in the application, which owns its own session. Neither is treated as redundant.
2. **Application sessions are server-side and revocable**: session store with idle and absolute timeouts, session-ID regeneration on login, real revocation on logout and on credential change — this closes SEC-002 by promotion from follow-up to prerequisite.
3. **Cookie contract**: server-set `__Host-` cookie, `Secure`, `HttpOnly`, `SameSite=Lax`, ≥64 bits of CSPRNG entropy.
4. **Authentication factors**: **passkey-first** (WebAuthn), with TOTP as the recovery path; Argon2id for any password material that remains. ADR-006's password becomes a fallback login, not the primary one.
5. **API semantics for clients**: 401 (never a 302) for unauthenticated XHR, so a PWA can prompt instead of silently rendering a login page into a fetch call. The `X-API-KEY` surface from ADR-004/006 is replaced by **one scoped, hashed, revocable, read-only agent token** for LLM/agent tooling.
6. **A committed break-glass path**: a second IngressRoute without the forward-auth middleware, restricted to the VPN, plus `kubectl port-forward` as the emergency route — both of which must survive GitOps reconciliation, and both exercised at least once during phase 3.
7. **Sharing in v1 is an export, not a route.** An age-encrypted PDF/CSV (optionally FHIR-shaped JSON for a future clinician) generated on demand. **No share route exists in v1.**
8. **Auth and share lifecycle events are logged** into `auth_audit` (login success/failure, session create/destroy, token issue/revoke, export generated) — cheap now, and exactly the table retrofitting multi-user would otherwise force.
9. **Multi-user is rejected as a scope item**, with a named trigger to reopen: *a second person's own data must live in the system*. Merely "someone wants to see mine" is served by an export or, at most, the aggregate demo in ADR-007.
10. **A public surface is aggregates only**, from a separate deployment and database, documented as permanent and correlatable (ADR-007 §4).
11. **Two routes, one deployment (SC-04).** The application is deployed once and exposed twice: a **tailnet route** — a name resolving inside the VPN to the tailnet address, carrying `vpn-whitelist` plus Authelia at `one_factor` with a long session, so daily use on the phone has no prompt — and a **public route** at `two_factor` for devices that cannot join the mesh. Neither exposes data unauthenticated; only the login page is public. The floor this sets: no public data surface exists in v2, and no share route exists at all.

## Consequences

### Positive

- A single misconfigured middleware policy is no longer a full data exposure: it takes two independent failures.
- Revocation, recovery and account-change paths exist before the data that makes them matter arrives.
- The most likely real sharing need (a doctor, once) is met without ever publishing an endpoint onto health data.

### Negative

- More authentication machinery than a single-user app "needs" — passkeys, a session store, an audit table, a break-glass route to maintain.
- Passkey-in-an-installed-PWA behaviour on the owner's phone is **unverified** and must be tested before passkeys become the only path (see the target architecture, §12, M-series measurements).

### Neutral

- The break-glass route is a permanent, deliberate hole restricted to a private network. It is documented rather than hidden, which is the only defensible version of it.

## References

- `docs/architecture/research/06-access-privacy-and-sharing.md`
- `docs/architecture/target-architecture-v2.md` §9, §15 (**SC-04**) · register: SC-04, SC-12
- `docs/adr/adr-006-single-user-session-gate.md`, `docs/adr/adr-011-deployment-topology.md`
- Issues: SEC-002 (#49), SEC-003 (#50), SEC-004 (#51) — SEC-002 becomes a prerequisite rather than a follow-up
