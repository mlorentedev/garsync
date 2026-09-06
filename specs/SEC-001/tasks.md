---
tags: [spec, tasks]
created: "2026-08-27"
---

# Tasks - SEC-001

> TDD order. One task = one focused commit. Order frozen (status: implementing).

## Setup

- [x] Branch created: `feat/sec-001-auth-gate`
- [x] `proposal.md` complete, acceptance criteria testable
- [x] No open questions left (all resolved in proposal §Risks)

## Implementation

- [x] [P] [AC4] Failing test: API key strict mode — `GARSYNC_API_KEY` set + missing header → 401, wrong key → 403, right key → 200; unset `GARSYNC_API_KEY` + unset access password → open with warning logged
- [x] [AC4] Implement: `compare_digest` comparison, remove `dev_key` fallback, 401-vs-403 semantics
- [x] [AC1] Failing test: unauthenticated GET `/` → 302 `/login`; unauthenticated GET `/api/activities` → 401
- [x] [AC1] Implement: session gate middleware (cookie check before routers/static), signed-cookie token module (stdlib HMAC, expiry embedded)
- [x] [AC2] Failing test: `POST /login` correct password → Set-Cookie (HttpOnly, SameSite=Lax, Secure) + 303 to `/`; wrong password → 401 + `{{ERROR}}` rendered
- [x] [AC2] Implement: `/login` GET+POST (token-replacement page rendering), `/logout` POST (clears cookie)
- [x] [AC3] Failing test: 5 failed POSTs → 6th → 429
- [x] [AC3] Implement: in-memory per-IP limiter (window 5 min)
- [x] [P] [AC5] Failing test: CORS — env unset → no CORS headers; env set → only allowlisted origin echoed; `*` never honored with credentials
- [x] [AC5] Implement: `GARSYNC_ALLOWED_ORIGINS` wiring in `create_app`
- [x] [P] [AC6] Failing test: `/api/activities?start_date=garbage` → 422
- [x] [AC6] Implement: `datetime.date` typing on all date query params across routes
- [x] Integrate login page (review `specs/SEC-001/notes/login-page-draft.html`, inlined in `src/garsync/api/auth.py` with `{{ERROR}}` replacement)
- [x] Update existing tests broken by fallback removal / 401-vs-403 change (`tests/api/conftest.py`, `tests/test_integration_full.py`)

## Closing

- [x] Every AC covered by ≥1 test
- [x] `features.json` filled with non-vacuous verification commands (pytest targets per AC)
- [x] Type checks pass (mypy --strict)
- [x] Lint passes (ruff)
- [x] No unrelated changes in diff
- [x] `verification.md` filled with evidence
- [ ] PR opened referencing specs/SEC-001 and #39  ← awaiting commit approval (house commit policy: stage/commit needs owner sign-off)
