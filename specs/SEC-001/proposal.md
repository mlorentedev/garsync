---
id: "SEC-001"
type: spec
status: implementing
created: "2026-08-27"
issue: "mlorentedev/garsync#39"
tags: [spec, proposal]
template_version: "1.0"
---

# SEC-001

## Why

GarSync will be deployed publicly on NaN Cloud Apps (DEPLOY-001): one public HTTPS URL. Today the static dashboard is served unauthenticated, `/api/*` trusts a header whose value falls back to a known constant (`dev_key`) when the env is unset, comparisons are not constant-time, and CORS allows any origin with credentials. On a public URL this means anyone can see the dashboard and the API key provides no real protection. Owner must be the only person with access (session: 2026-08-27, decision "Opción A": app password, NOT Garmin-credentials login — Garmin SSO brute-force/lockout risk + datacenter-IP captchas rejected it). Issue: mlorentedev/garsync#39. Deployment target and threat model: docs/runbooks + NaN Cloud Apps facts in vault `00_meta/patterns/pattern-nan-cloud-apps.md`.

## What

1. Unauthenticated request to any page (static dashboard included) → redirect to `/login` (the landing IS the login form). Unauthenticated `/api/*` → 401 JSON. Wrong credentials provided → 403.
2. `POST /login` with `GARSYNC_ACCESS_PASSWORD` → HttpOnly + SameSite=Lax + Secure signed session cookie (stdlib HMAC, no new deps) → dashboard works; `POST /logout` clears it.
3. Login POST rate-limited in-memory per IP (single replica): 5 failures / 5 min → 429.
4. `X-API-KEY` remains valid for programmatic `/api/*` access; compared via `secrets.compare_digest`; the `dev_key` fallback disappears — no auth env at all → app runs unprotected with a loud startup warning (local-dev convenience, fail-open only when BOTH `GARSYNC_ACCESS_PASSWORD` and `GARSYNC_API_KEY` are unset; documented in runbook that NaN deployment MUST set the password).
5. CORS: `GARSYNC_ALLOWED_ORIGINS` (comma list) drives the middleware; unset → no CORS middleware (same-origin app); wildcard impossible.
6. Date query params on `/api/*` routes typed `datetime.date` → malformed input returns 422, never 500.

## Out of scope

- Scheduler + sync trigger endpoint + pipeline transactions (SYNC-001)
- Garmin-credentials-as-login (rejected design, see session 2026-08-27)
- TOTP/second factor (noted as future hardening; trivial to add later)
- TLS/domain (NaN platform provides automatic HTTPS)
- Password rotation UI (rotation = change env + redeploy)
- Astro/frontend build changes (login page served by FastAPI with token replacement, no jinja2 dep)

## Risks / open questions

- Existing API tests pass auth via header/default — they will be updated in this spec (scoped task).
- 401-vs-403 semantics: 401 = no credentials presented, 403 = credentials presented but invalid (change from current blanket 403; issue AC only pins 401 for unauthenticated).
- In-memory rate limiter resets on process restart — accepted with 1 replica (NaN Apps).
- Session signing key derived from `GARSYNC_ACCESS_PASSWORD` → password rotation invalidates sessions (accepted, documented).
- Cookie `Secure` flag: always on (NaN is HTTPS). Local dev that sets a password over plain http needs `GARSYNC_INSECURE_COOKIES=1` escape hatch (runbook note).
- Backend string-replaces `{{ERROR}}` token in the login page HTML (no jinja2 dep) — page draft under `specs/SEC-001/notes/`.

## Acceptance criteria

- [ ] AC1: Unauthenticated dashboard request → 302 `/login`; unauthenticated `/api/*` → 401 JSON
- [ ] AC2: Correct password → session cookie → dashboard renders; logout clears access
- [ ] AC3: 5 failed logins → 6th returns 429
- [ ] AC4: No `dev_key` fallback; all credential comparisons constant-time (`secrets.compare_digest`)
- [ ] AC5: CORS wildcard impossible; allowlist driven by `GARSYNC_ALLOWED_ORIGINS` only
- [ ] AC6: Malformed date query → 422

## References

- Issue: mlorentedev/garsync#39 (work gate, self-assigned)
- Secrets hardening (session 2026-08-27): dedicated age identity `~/.config/age/garsync.txt`, file re-keyed via `sops updatekeys`, master ecosystem key can no longer decrypt this repo
- Related: SYNC-001 (#37) scheduler, DEPLOY-001 (#38) NaN deploy runbook
- Vault: `00_meta/patterns/pattern-nan-cloud-apps.md` (no platform auth for Apps → app-level gate mandatory)
