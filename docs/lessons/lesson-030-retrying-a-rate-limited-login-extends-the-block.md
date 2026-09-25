---
id: lesson-030-retrying-a-rate-limited-login-extends-the-block
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, garmin, rate-limits, retries, ingestion, ops]
---

# Retrying a rate-limited login extends the block

Measured in `specs/SUB-002`, on the first live login attempt of the session.

- **Finding.** Garmin Connect's login is currently refused at the network edge, and the client's own
  retry ladder multiplied the request count:

  ```
  mobile+cffi   returned 429: GarminConnectTooManyRequestsError — Mobile login returned 429
  widget+cffi   failed:      unexpected title 'GARMIN Authentication Application'
  portal+cffi   returned 429: Portal login GET returned 429 — Cloudflare blocking this request.
  portal+requests failed:    Portal login: HTTP 403 (Cloudflare bot challenge)
  → "All login strategies exhausted"   (×3 tenacity attempts, ≈12 rejected requests in seconds)
  ```

  Every strategy was tried, three times each, against a surface that had already answered "too many
  requests". The mechanism that exists to survive a flaky network is what deepens a rate-limit block —
  and there is no `garmin_tokens.json` on disk in this checkout, so the credential path is the *only*
  path.

- **Why it matters beyond one blocked afternoon.** `ADR-008` §8's posture is "token caching, a login
  fallback chain, exponential backoff on 429". An exponential retry **on 429** is a contradiction, and
  the deployment story inherits it: a password login from a datacenter IP will meet exactly this edge.
  The right reading is *classify before retrying* — a rate-limit or bot-challenge answer means stop and
  reuse a token, while a connection reset or a 5xx means retry.

- **Pattern.** Retry transient failures; never retry a refusal. Log each attempt with its strategy name
  (that log is the only reason the ~12 requests are countable here), keep a token cache as the primary
  path, and treat the credential path as the fallback it is. When a capability cannot be measured
  because of this, record it as *blocked* with the observed status codes rather than as *absent*.

**Tags:** `#garmin` `#rate-limits` `#retries` `#ingestion` `#ops`
