---
id: "SEC-001"
type: spec
status: archived
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
4. `X-API-KEY` remains valid for programmatic `/api/*` access, compared in **constant time over UTF-8 bytes** so that any value a client can send — including non-ASCII — is rejected rather than raising (see the 2026-09-25 review round in §Risks); the `dev_key` fallback disappears — with **neither** `GARSYNC_ACCESS_PASSWORD` nor `GARSYNC_API_KEY` set the app runs unprotected with a loud startup warning (local-dev convenience, documented in the runbook as acceptable only on a trusted network). With **only** the API key set, `/api/*` requires it while the dashboard pages are served unauthenticated: that state is warned about at startup and documented in `docs/deploy-self-hosted.md` §Environment, and closing it outright is tracked as [SEC-004 (#51)](https://github.com/mlorentedev/garsync/issues/51) — [ADR-010](../adr/adr-010-access-and-sharing-model.md) decides that the dashboard always requires a session, so the API key is a machine credential and never a page one.
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

- **Stateless sessions cannot be revoked before they expire (accepted, tracked).** The session token is an
  HMAC over its own expiry, so `POST /logout` clears the cookie but a stolen copy stays valid until it
  expires. This was a deliberate trade for shipping the gate without a session store; ADR-010 makes
  server-side revocable sessions a **prerequisite** for the deployed instance, and the work is
  [SEC-002 (#49)](https://github.com/mlorentedev/garsync/issues/49), folded into the access work of
  DEPLOY-002. Reviewed and raised by the adversarial review of 2026-09-25 (Minor).
- **The login rate limiter counts the address the request arrives from (tracked).** Behind the reverse
  proxy every deployment target uses, `request.client.host` is the proxy's address, so all attempts share
  one counter and the owner can lock themselves out. Tracked as
  [SEC-003 (#50)](https://github.com/mlorentedev/garsync/issues/50) with the finding's evidence and a fix
  sketch; it is a deployment-shape issue, which is why it lands with DEPLOY-002 rather than here.
- **`POST /login` buffers at most 4 KiB of body** (`MAX_LOGIN_BODY_BYTES`); an oversized body is treated as
  a failed attempt. Added after the 2026-09-25 review pointed out that the only unauthenticated write path
  had no limit of its own.
- Existing API tests pass auth via header/default — they were updated in this spec (scoped task).
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

<!-- archived 2026-09-23 — PR: https://github.com/mlorentedev/garsync/pull/111 -->
