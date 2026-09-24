---
spec: "SEC-001"
verdict: "FAIL"
reviewed_sha: "f74ba75a8c90399c583026836d836c53cef4ad45"
reviewer: "agy/gemini-3.1-pro-high"
date: "2026-09-23"
---

## Adversarial review

**Scope**: SEC-001
**Sources**: `specs/SEC-001/proposal.md`, `specs/SEC-001/tasks.md`, `specs/SEC-001/verification.md`, PR diff 6a0ac67f441503ce0cf0f131297221e8c97285ba...HEAD

### Spec and task alignment
- All acceptance criteria are nominally implemented and covered by tests.
- However, a critical flaw in the use of `hmac.compare_digest` breaks the authentication mechanisms when exposed to non-ASCII input, violating the reliability and correctness of AC2 and AC4.
- The fail-open behavior slightly mismatches the proposal wording (dashboard is unauthenticated if only the access password is unset, whereas AC4 states fail-open occurs only when BOTH are unset).

### Findings

| Severity | Reality | Area | Finding | Evidence | Test (named, or UNTESTED) | Fix location (code / tests / spec / vault) |
|----------|---------|------|---------|----------|---------------------------|---------------------------------------------|
| Blocker | REAL | auth | `hmac.compare_digest` raises `TypeError` (500 Internal Server Error) when either string contains non-ASCII characters. This creates an unauthenticated DoS vector via `Cookie: garsync_session=123.ñ` or `password=ñ` and bypasses the rate limiter (it crashes before `record_failure`). | Reproduced locally: sending non-ASCII password triggers 500 error instead of 401. | UNTESTED | code + tests (encode strings to bytes before `compare_digest` in `main.py` and `auth.py`, add `test_password_non_ascii_crash`) |
| Major | REAL | auth | (Known F1 from previous review) Rate limiter keys on `request.client.host`, which behind a reverse proxy blocks all users. | `src/garsync/api/main.py:123` | UNTESTED | Tracked in SEC-003 (#50) |
| Minor | THEORETICAL | auth | Stateless session tokens cannot be revoked on logout; they remain valid until expiry. A stolen cookie remains valid even after the user logs out. | `src/garsync/api/main.py:155` | UNTESTED | spec (document risk in proposal) |
| Minor | SPECULATIVE | perf | `POST /login` reads the entire request body into memory (`await request.body()`), which could cause OOM if the reverse proxy doesn't enforce a client body size limit. | `src/garsync/api/main.py:130` | UNTESTED | code (use `request.form()`) |
| Minor | THEORETICAL | spec | Spec mismatch: AC4 says "fail-open only when BOTH are unset", but if only `GARSYNC_ACCESS_PASSWORD` is unset, the dashboard is unprotected while the API remains protected. | `src/garsync/api/main.py` | UNTESTED | spec (update AC4) |

### Evaluator rubric

| Dimension | Grade (A-D) | Rationale (one line) |
|-----------|-------------|----------------------|
| Correctness        | D | `hmac.compare_digest` crashes on non-ASCII input, bypassing intended auth flow and causing 500 errors. |
| Verification       | A | Evidence proves each criterion with reproducible commands and tests. |
| Scope              | B | Diff mostly matches; minor fail-open condition mismatch. |
| Reliability        | D | Crashes on fuzzed/non-ASCII input (DoS vector). |
| Maintainability    | A | Clear naming, logic is contained, CC is low. |
| Handoff-readiness  | B | Spec is updated, but contains minor mismatches with implementation. |

### Verdict
FAIL

### Recommended next steps
- **Code + Tests**: Fix the `TypeError` in `compare_digest` by encoding inputs to `utf-8` bytes before comparison (e.g., `a.encode('utf-8') if isinstance(a, str) else a`) in `src/garsync/api/main.py` (API key) and `src/garsync/api/auth.py` (session signature and login password). Add negative tests proving 401/403 is returned for non-ASCII passwords and cookies instead of 500.
- **Spec**: Update AC4 in `proposal.md` to reflect that the dashboard remains unauthenticated if only `GARSYNC_ACCESS_PASSWORD` is unset.
- **Spec**: Acknowledge the stateless token replay risk in `proposal.md`'s Risks section.
- **Do not archive** the spec (`dotf spec archive`) until the Blocker is addressed and a re-review passes.
