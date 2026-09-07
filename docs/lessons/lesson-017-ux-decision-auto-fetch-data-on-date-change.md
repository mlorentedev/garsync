---
id: lesson-017-ux-decision-auto-fetch-data-on-date-change
type: lesson
status: active
created: "2026-05-29"
recorded: "2026-03-01"
owner: manu
tags: [garsync, lesson, ux, frontend, decision]
---

# UX Decision: Auto-fetch Data on Date Change

> Recorded 2026-03-01 in the flat `docs/lessons.md`; first appeared in git on 2026-05-29.

**Context:** Dashboard date range filtering UX.

**Problem:** User disliked having to run `make sync` or click buttons to load data. The mental model was: "I pick dates, data appears."

**Solution:** Date inputs should trigger data fetching reactively — no explicit sync action needed. Changing date range = automatic API call to load matching data.

**Why:** The sync-then-view model adds friction. For a personal dashboard, reactive data loading on date change is the expected UX. `make sync` remains for CLI-only bulk imports from Garmin Connect, but the dashboard should never require it.

**Tags:** `#ux` `#frontend` `#decision`
