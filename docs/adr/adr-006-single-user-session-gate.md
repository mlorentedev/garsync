---
id: adr-006-single-user-session-gate
type: adr
status: active
created: "2026-08-27"
owner: manu
---

# ADR-006: Single-User Session Gate with an Application Password

## Status
Accepted (decided 2026-08-27, shipped in v0.2.0 via PR #44, spec `specs/SEC-001`). Amends [ADR-004](adr-004-api-key-auth.md).

## Context
GarSync is to be deployed on a public HTTPS URL (NaN Cloud Apps, DEPLOY-001), and the platform provides no authentication layer of its own. Before this decision the static dashboard was served to anyone, `/api/*` trusted an `X-API-KEY` header that fell back to the constant `dev_key` when the environment was unset, key comparison was not constant-time, and CORS allowed any origin with credentials. The application serves the health data of exactly one person: the owner must be the only one with access.

Two designs were considered for the login step:

- **Option A: application password.** A dedicated secret, unrelated to Garmin, checked by GarSync itself.
- **Option B: Garmin credentials as the login.** Rejected. Proxying the owner's Garmin login through a public endpoint exposes the Garmin account to brute-force attempts and lockout, and Garmin serves captchas to datacenter IPs, so the flow would be unreliable exactly where it is deployed.

## Decision
1. A single application password, `GARSYNC_ACCESS_PASSWORD`, gates every page. Unauthenticated requests to the dashboard redirect to `/login`; unauthenticated requests to `/api/*` receive 401 JSON. Credentials that are present but wrong receive 403.
2. A successful login issues a stateless session token signed with stdlib HMAC and keyed by the password, carried in an `HttpOnly; SameSite=Lax; Secure` cookie with a 7-day expiry embedded in the token. No new dependencies. Rotating the password invalidates all sessions; `GARSYNC_INSECURE_COOKIES=1` drops the `Secure` flag for local development only.
3. Login attempts are rate-limited in memory per client IP (5 failures in 5 minutes, then 429). Accepted trade-off for a single replica: the counter resets on restart.
4. The `X-API-KEY` credential from ADR-004 stays valid for programmatic `/api/*` access. Its `dev_key` fallback is removed and all comparisons use `secrets.compare_digest`.
5. CORS is opt-in through `GARSYNC_ALLOWED_ORIGINS`. Unset means no CORS middleware (same-origin application). A wildcard is rejected at startup because requests are credentialed.
6. The application fails open, with a loud startup warning, only when both `GARSYNC_ACCESS_PASSWORD` and `GARSYNC_API_KEY` are unset. This keeps local development frictionless while making an unprotected public deployment an explicit choice.

## Consequences
- **Pros:** The owner's Garmin account is never exposed through the public surface. No session store and no new runtime dependency. The whole gate is a few hundred lines of stdlib code that is easy to audit.
- **Cons:** Stateless tokens cannot be revoked individually on logout (SEC-002, #49). The rate limiter and origin handling are not proxy-aware yet (SEC-003, #50). The API-key-only configuration still serves the dashboard without a password and needs a decision (SEC-004, #51). A second factor is deliberately out of scope and can be added later.
- **Follow-ups:** SEC-003 must land before DEPLOY-001 makes the URL public. Deployment instructions live in `docs/deploy-self-hosted.md`.
