---
id: lesson-006-httpx-never-sends-secure-cookies-over-http
type: lesson
status: active
created: "2026-09-05"
owner: manu
tags: [garsync, lesson, testing, httpx, cookies]
---

# httpx never sends `Secure` cookies over `http://`

- **Context:** SEC-001 session cookie tests
- **Finding:** The session cookie is flagged `Secure` (production posture). Tests pointed the httpx client at `http://test`, so the cookie was stored but never sent back — auth tests failed with a misleading 401 while login returned 303.
- **Pattern:** Test Secure-cookie flows against an `https://` base_url, matching the real deployment.

**Tags:** `#testing` `#httpx` `#cookies`
