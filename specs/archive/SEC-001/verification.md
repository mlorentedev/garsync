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
| AC6 | `tests/api/test_auth.py::TestDateValidation` (422 on malformed dates) + `test_garbage_date_returns_422_on_every_date_param` (parametrized over both date params of `/api/sleep` and `/api/stats/summary`, added 2026-09-25) | pass |

`features.json` states remain `pending` — they flip to `passing` only via harness verification runs of the listed commands.

## Adversarial review — first round (2026-09-25, `nan/mimo-v2.5`)

Run through `dotf spec review SEC-001` — the reviewer is drawn from `harness/reviewer-pool.json`, so it
is never the implementer and never an Anthropic model. This round: **`nan/mimo-v2.5`**, verdict
**PASS-WITH-GAPS**, `reviewed_sha` recorded in [`review.md`](review.md) (the review's own artifact, not
reproduced here, so the two cannot drift apart).

| Finding | Severity as returned | Disposition |
|---|---|---|
| **F1** — the login rate limiter keys on `request.client.host`, so behind a reverse proxy (the stated deployment target) every attempt shares the proxy's counter and the owner can lock themselves out | Major, REAL | **Tracked, not fixed here.** It is [SEC-003 (#50)](https://github.com/mlorentedev/garsync/issues/50) — *proxy-aware client IP for the rate limiter* — which the ticket plan already routes into the deployment work (DEPLOY-002), where the proxy topology is actually known. The issue now carries this finding's evidence and the fix sketch (`GARSYNC_TRUSTED_PROXY_COUNT`, default 1). It is not a gap in AC3, which is implemented and tested as specified |
| **F2** — the diff moved five routes from `str` to `datetime.date`; only two had a negative test | Major, THEORETICAL | **Applied**: `test_garbage_date_returns_422_on_every_date_param`, parametrized over **both** date params of the two uncovered routes. Verified by consequence — reverting `sleep.py`'s `start_date` to `str` fails the new test (it returns 500, not 422) |
| **F3** — `verify_session_token` has four failure branches and only the happy path was tested | Minor, THEORETICAL | **Applied**: `TestSessionTokenVerification` — valid, malformed/absent, tampered signature, wrong password, expired (via an injected `now`), and missing access password. Verified by consequence — neutering the expiry comparison fails the expiry test |
| **F4** — `period` accepts arbitrary strings and silently falls back | Minor, SPECULATIVE | **No action, with the reason recorded in the review.** AC6 covers *date* params; `period` is a bounded enum-shaped string with a safe default, and tightening it is a different change |

The review also re-confirmed the task list is fully ticked, that no `[AGENT-DRAFT]` tags remain, and that
AC1–AC5 map to named tests. Test count after this round: **141 passed** (128 before, +13: four
parametrized date cases and nine token-verification cases).

**Note on scope:** the review's diff window is everything since the spec's base commit, not only this
spec's files, so its findings can concern work that is not SEC-001's — F1 is the example, and routing it
to its own ticket rather than re-opening this spec is the disposition, not a dismissal.


## Adversarial review — second round (2026-09-25, `agy/gemini-3.1-pro-high`)

The first round (above) was PASS-WITH-GAPS and its actionable findings were closed. The re-run — on the provider-diverse arm of `harness/reviewer-pool.json`, drawn at random — returned
**FAIL**, and it was right to:

| Finding | Severity as returned | Disposition |
|---|---|---|
| **`hmac.compare_digest` raises `TypeError` on non-ASCII input**, turning `password=ñ`, a non-ASCII `X-API-KEY` header or a non-ASCII session cookie into an unhandled **500** — unauthenticated, and it slipped past the rate limiter because it threw before the failure was recorded | **Blocker**, REAL | **Fixed.** `constant_time_equals()` in `api/auth.py` compares UTF-8 encodings, and the three call sites (`api/main.py` header + login form, `api/auth.py` cookie signature) use it. Four regression tests in `TestNonAsciiInputDoesNotCrash` cover the four entry points — password, `X-API-KEY`, cookie, and a body that is not valid UTF-8 (`decode(..., errors="replace")`) — plus one proving the failed non-ASCII attempts now reach the limiter. RED first: all five failed against the unfixed code with exactly the reported `TypeError`/`UnicodeDecodeError` |
| The login rate limiter keys on the proxy's address (also round 1's F1) | Major, REAL | Tracked: SEC-003 (#50) |
| Stateless session tokens cannot be revoked before expiry | Minor, THEORETICAL | Tracked: SEC-002 (#49), and ADR-010 makes server-side sessions a prerequisite. Now also recorded in `proposal.md` §Risks |
| `POST /login` buffered an unbounded body | Minor, SPECULATIVE | **Fixed**: `MAX_LOGIN_BODY_BYTES = 4096`, with an oversized body counted as a failed attempt (so the reply is not an oracle). Test: `test_oversized_login_body_is_rejected_not_buffered` |
| AC4's wording did not describe the API-key-only state | Minor, spec | **Fixed in the spec**: AC4 now states that with only the API key set, `/api/*` is protected and the pages are not, that the runbook documents it, and that closing it is SEC-004 (#51) with ADR-010's answer |

Suite after this round: **147 passed** (128 before the spec's review rounds).

**Side effect worth recording:** the reviewer ran with `--dangerously-skip-permissions` and wrote into the
working tree — a probe test (`tests/api/test_hmac_crash.py`, whose scenario is now covered properly by
`TestNonAsciiInputDoesNotCrash`) and five scratch dumps (`*.py.txt`, `tests_diff.txt`). All were removed
before this commit, and `.gitignore` now excludes the review's own state files (`review-transcript.jsonl`,
`review-request.json`) per the fleet convention while keeping `review.md` tracked. Anyone who runs
`dotf spec review` should check `git status` afterwards, not assume the tree is theirs alone.

## Security notes

- Session tokens: HMAC-SHA256 keyed by the access password; rotation invalidates all sessions (accepted, proposal §Risks).
- All credential comparisons are constant-time over UTF-8 bytes (`constant_time_equals`, wrapping `hmac.compare_digest`), because `compare_digest` rejects non-ASCII `str` input by raising — see the second review round above.
- Cookies: HttpOnly + Secure + SameSite=Lax; `GARSYNC_INSECURE_COOKIES=1` is the local-http escape hatch (runbook note).
- Rate limiter is in-memory, per-`create_app` instance (resets on restart; single replica on NaN Apps).
- Garmin credentials never enter the web process: SOPS decryption belongs to the sync subprocess (SYNC-001 wires the scheduler).
- Remaining known limits: single factor (no TOTP — future hardening), in-memory limiter not shared across replicas.
