---
id: "SEC-001"
type: spec
status: verifying
created: "2026-08-27"
issue: "mlorentedev/garsync#39"
tags: [spec, verification]
template_version: "1.0"
---

# SEC-001 — Verification

## Evidence (2026-08-28, this session)

```
$ make check
  lint ........... ok
  type ........... ok
  test ........... 127 passed in 1.11s
  astro-check .... 0 errors
  astro-build .... ok
✓ All checks passed
```

TDD trace: RED phase produced 13 failing tests (401/403 semantics absent, no /login route, no rate limit, CORS wildcard, unvalidated str dates) before any implementation; GREEN landed in `src/garsync/api/auth.py` (session tokens, rate limiter, login page) + `main.py` (gate middleware, routes, conditional CORS) + route date typing + `frontend/src/lib/api.ts` dev_key fallback removal.

## AC mapping

| AC | Test(s) | Status |
|---|---|---|
| AC1 | `tests/api/test_auth.py::TestSessionGate` (302 + 401) | pass |
| AC2 | `tests/api/test_auth.py::TestLoginFlow` (cookie flags, error render, logout revoke) | pass |
| AC3 | `tests/api/test_auth.py::TestLoginRateLimit` (6th attempt 429) | pass |
| AC4 | `tests/api/test_auth.py::TestApiKeyStrict` (401/403/200, open-mode warning) | pass |
| AC5 | `tests/api/test_cors.py` (disabled / allowlisted / denied) | pass |
| AC6 | `tests/api/test_auth.py::TestDateValidation` (422) | pass |

`features.json` states remain `pending` — they flip to `passing` only via harness verification runs of the listed commands.

## Security notes

- Session tokens: HMAC-SHA256 keyed by the access password; rotation invalidates all sessions (accepted, proposal §Risks).
- All credential comparisons constant-time (`hmac.compare_digest`): API key and cookie signature.
- Cookies: HttpOnly + Secure + SameSite=Lax; `GARSYNC_INSECURE_COOKIES=1` is the local-http escape hatch (runbook note).
- Rate limiter is in-memory, per-`create_app` instance (resets on restart; single replica on NaN Apps).
- Garmin credentials never enter the web process: SOPS decryption belongs to the sync subprocess (SYNC-001 wires the scheduler).
- Remaining known limits: single factor (no TOTP — future hardening), in-memory limiter not shared across replicas.
