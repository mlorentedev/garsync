---
id: lesson-001-garmin-api-response-format-inconsistencies
type: lesson
status: active
created: "2026-05-29"
owner: manu
tags: [garsync, lesson, garmin-api, client]
---

# Garmin API response format inconsistencies

- **Context:** `client.py` fetch methods
- **Finding:** Garmin API returns body battery as list of dicts sometimes, single dict others. HR data can have missing `restingHeartRate` key entirely.
- **Pattern:** Always use `.get()` with defaults, handle both list and dict formats, catch per-record parsing errors without blocking the full sync.

**Tags:** `#garmin-api` `#client`
