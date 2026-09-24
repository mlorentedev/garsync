---
id: lesson-024-compare-digest-raises-on-non-ascii-input
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, python, security, auth, testing, gotcha]
---

# `hmac.compare_digest` raises on non-ASCII `str`, turning an auth check into an unauthenticated 500

- **Context:** adversarial review of `specs/SEC-001` (round 2, `agy/gemini-3.1-pro-high`), which returned
  **FAIL**. The auth code used the textbook-correct constant-time comparison everywhere — and that is
  exactly what made it crash.
- **Finding:** `hmac.compare_digest` refuses `str` arguments containing non-ASCII characters and raises
  `TypeError: comparing strings with non-ASCII characters is not supported`. `str` support was removed
  precisely because non-ASCII `str` has no single canonical byte encoding, so CPython rejects it instead
  of guessing. In an auth check that raises on **attacker-controlled input**, which is an unauthenticated
  500 — and because the comparison ran *before* the failure was recorded, it also walked past the login
  rate limiter. Four reachable entry points, each reproduced with a real request:

  | Input a client can send | Where it arrives |
  |---|---|
  | `POST /login` form field `password=ñ` — percent-encoded UTF-8, which is what a browser sends | the login handler |
  | `X-API-KEY: <non-ASCII>` — HTTP header values are latin-1 on the wire | the API-key gate |
  | `Cookie: garsync_session=1800000000.ñ` | the session-token verifier, i.e. every request |
  | a login body that is not valid UTF-8 (`b"password=\xff"`) | `body.decode()`, the same endpoint |

- **Pattern:** compare **bytes**, never `str`, on any value a client can influence:
  `hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))`. The constant-time property holds over the
  encoded bytes; only length remains observable, which it also is for `compare_digest` on equal-length
  inputs. Decode with `errors="replace"` (or catch `UnicodeDecodeError`) wherever a body is decoded, and
  cap what an unauthenticated endpoint will buffer. More generally, an auth endpoint needs a **hostile
  input class** in its tests — non-ASCII, invalid UTF-8, oversized, empty — because a 500 on that path is
  both a denial of service and an information leak, and no functional test will ever produce one.
- **Testing gotcha, worth its own line:** the first draft of the regression tests used httpx's
  conveniences (`data={"password": "ñ"}`, `cookies.set(...)`) and failed **inside httpx** with
  `UnicodeEncodeError` before any request was built. The tests looked green-adjacent and exercised
  nothing. Send raw bytes (`content=b"password=%C3%B1"`, `headers={b"X-API-KEY": b"clave-\xf1"}`) — that is
  what reaches the server, and it is what made the RED phase show the real `TypeError`.

**Tags:** `#python` `#security` `#auth` `#testing` `#gotcha`
