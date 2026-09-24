---
spec: "SEC-001"
verdict: "PASS"
reviewed_sha: "ca221778c4b0c7c1e3dd2ef44c39bcb72270962e"
reviewer: "nan/mimo-v2.5"
date: "2026-09-23"
---

## Adversarial review

**Scope**: SEC-001 (third round — full diff from base `6a0ac67f`)
**Sources**: `specs/SEC-001/proposal.md`, `specs/SEC-001/tasks.md`, `specs/SEC-001/verification.md`, `specs/SEC-001/features.json`, `git diff 6a0ac67f...HEAD` (102 files, ~7k added / ~1.5k removed)

### Spec and task alignment

All six acceptance criteria are implemented, tested, and verified:

| AC | Implementation | Named test(s) | Evidence |
|---|---|---|---|
| AC1 | `auth_gate` middleware: unauthenticated `/` → 302 `/login`; unauthenticated `/api/*` → 401 | `TestSessionGate` (2 tests) | pass |
| AC2 | `login_submit`: correct password → signed cookie → 303; wrong → 401; `logout` clears cookie | `TestLoginFlow` (4 tests) | pass |
| AC3 | `LoginRateLimiter`: 5 failures in 5 min → 6th → 429 | `TestLoginRateLimit` (1 test) | pass |
| AC4 | No `dev_key` fallback; `constant_time_equals` wraps `compare_digest` over UTF-8 bytes; 401/403 semantics | `TestApiKeyStrict` (4 tests) + `TestNonAsciiInputDoesNotCrash` (6 tests) | pass |
| AC5 | `GARSYNC_ALLOWED_ORIGINS` drives CORS middleware; `*` raises `ValueError` at startup; unset → no middleware | `test_cors.py` (4 tests) | pass |
| AC6 | All date query params typed `datetime.date` → malformed → 422 | `TestDateValidation` (6 tests, parametrized) | pass |

Additional coverage beyond ACs: `TestSessionTokenVerification` (9 tests covering valid, malformed, tampered, wrong-password, expired, missing-password tokens) and `TestNonAsciiInputDoesNotCrash` (6 tests covering non-ASCII password, API key, cookie, oversized body, undecodable body, and rate-limiter bypass via crash). Total suite: **147 tests, all passing**.

Tasks.md: all boxes ticked, including the closing tasks. No `[AGENT-DRAFT]` tags remain in any spec file. `features.json` states are `pending` (correct — they flip via harness verification runs, not spec review).

### Findings

| Severity | Reality | Area | Finding | Evidence | Test (named, or UNTESTED) | Fix location |
|----------|---------|------|---------|----------|---------------------------|--------------|
| Minor | THEORETICAL | timing | Rate-liter timing leak: a blocked request (429) returns ~2× faster than a wrong-password request (401) because the block check runs before password comparison. An attacker measuring response time can distinguish "blocked" from "wrong password" and know when to wait. In practice, network jitter (>10ms) dominates the ~0.2µs difference, making this unexploitable over the internet. | `poetry run python3` benchmark: `is_blocked` 0.4µs/1k vs `constant_time_equals` 0.2µs/1k | UNTESTED | — (inherent to fail-fast rate limiting; no fix without adding a constant-time delay to the blocked path, which trades a timing leak for a DoS amplification vector) |
| Minor | THEORETICAL | auth | The 403 response on wrong `X-API-KEY` reveals that an API key is configured. A 401 (missing header) could mean "key required but not sent" or "no key configured, use session". An attacker can distinguish the two states. This is by design per AC4 semantics and documented in the proposal. | `auth_gate` middleware: `provided is not None` branch returns 403 on mismatch | `TestApiKeyStrict::test_wrong_key_returns_403` | spec (accepted by design) |

No Blockers or Majors found. Both previous review rounds' findings are dispositioned:

- **Round 1** (nan/mimo-v2.5, 2026-09-25): F1 (proxy blind rate limiter) → SEC-003 (#50); F2 (incomplete date test coverage) → applied; F3 (session token branches) → applied; F4 (period param) → no action with reason.
- **Round 2** (agy/gemini-3.1-pro-high, 2026-09-25): Blocker (compare_digest TypeError) → fixed in `ca221778`; Major (proxy blind rate limiter) → SEC-003 (#50); Minor (stateless token) → SEC-002 (#49); Minor (unbounded body) → fixed with `MAX_LOGIN_BODY_BYTES`; Minor (AC4 wording) → fixed in proposal.md.

### Evaluator rubric

| Dimension | Grade | Rationale (one line) |
|-----------|-------|----------------------|
| Correctness        | A | All six ACs verified with negative paths; non-ASCII crash (prior Blocker) fixed and regression-tested |
| Verification       | A | 147 tests, all passing; every AC mapped to named test classes; prior-review regressions explicitly verified by consequence (revert proves test catches the defect) |
| Scope              | A | Diff matches proposal exactly; non-SEC-001 changes (ADRs, deps, hygiene) are separate commits with clear boundaries |
| Reliability        | A | Error paths handled (malformed tokens, non-ASCII input, oversized bodies, undecodable bodies); constant-time comparisons throughout; fail-closed on every edge |
| Maintainability    | A | All functions < 40 lines; `auth.py` (186 lines) and `auth_gate` (40 lines) are well-structured; clear docstrings explain *why* each guard exists |
| Handoff-readiness  | A | Proposal, tasks, verification all current; two prior reviews dispositioned; SEC-002/003/004 tracked as follow-ups |

### Verdict
PASS

### Recommended next steps

- **Archive readiness**: `dotf spec archive SEC-001` is advisable. No Blockers or Majors remain; all prior findings are dispositioned; the two Minor findings (timing leak, 403 info leak) are tracked and accepted by design.
- **Follow-up tickets** (already open):
  - SEC-002 (#49): server-side revocable sessions (prerequisite for deploy per ADR-010)
  - SEC-003 (#50): proxy-aware client IP for rate limiter (`X-Forwarded-For` / `X-Real-IP` parsing)
  - SEC-004 (#51): dashboard auth when only API key is set (close the gap ADR-010 identifies)
- **No contract-set edits needed**: `proposal.md`, `tasks.md`, and `features.json` are correct as-is. The Minor findings do not warrant spec changes.
