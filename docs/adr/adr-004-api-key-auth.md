---
id: adr-004-api-key-auth
type: adr
status: active
created: "2026-03-07"
owner: manu
---

# ADR-004: Simple API Key Authentication

## Status
Accepted (implemented 2026-03). Amended by [ADR-006](adr-006-single-user-session-gate.md): the `dev_key` fallback anticipated below was removed, comparisons are constant-time, and the API key is now one of two credentials next to the password-based session gate.

## Context
GarSync exposes personal health and fitness data via a FastAPI REST API. Currently, these endpoints are public. While the primary use case is local/self-hosted, accidental exposure to the internet or unauthorized local access poses a privacy risk.

## Decision
We will implement a simple API Key authentication layer using a custom header `X-API-KEY`.
- The key will be configurable via an environment variable `GARSYNC_API_KEY`.
- If the variable is not set, a warning will be issued, but for ease of initial setup, it might remain optional or have a default "insecure" value in dev.
- All frontend requests will be updated to include this header.

## Consequences
- **Pros:** Basic protection against unauthorized data access.
- **Cons:** Requires managing an additional secret. Slight overhead in frontend API calls.
