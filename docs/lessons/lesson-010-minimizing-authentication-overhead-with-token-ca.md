---
id: lesson-010-minimizing-authentication-overhead-with-token-ca
type: lesson
status: active
created: "2026-05-29"
recorded: "2026-03-07"
owner: manu
tags: [garsync, lesson, authentication, caching, garmin-api, performance]
---

# Minimizing Authentication Overhead with Token Caching

> Recorded 2026-03-07 in the flat `docs/lessons.md`; first appeared in git on 2026-05-29.

**Context:** Implementing session token caching in GarminClient.

**Problem:** Frequent logins to Garmin Connect using email and password can lead to rate limiting or temporary account blocks. Re-authenticating on every sync is inefficient.

**Solution:** Modified GarminClient to support token-based authentication via garth. On first run, it authenticates with credentials and saves the session tokens to a JSON file. Subsequent runs use these tokens if they are valid, falling back to credentials only if necessary. This minimizes the risk of account blocks and speeds up the authentication step.

**Tags:** `#authentication` `#caching` `#garmin-api` `#performance`
