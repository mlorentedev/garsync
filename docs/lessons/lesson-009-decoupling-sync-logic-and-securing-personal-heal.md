---
id: lesson-009-decoupling-sync-logic-and-securing-personal-heal
type: lesson
status: active
created: "2026-05-29"
recorded: "2026-03-07"
owner: manu
tags: [garsync, lesson, refactor, security, fastapi, cli]
---

# Decoupling Sync Logic and Securing Personal Health APIs

> Recorded 2026-03-07 in the flat `docs/lessons.md`; first appeared in git on 2026-05-29.

**Context:** Refactoring CLI and adding API Key security to GarSync.

**Problem:** CLI logic was tightly coupled with DB operations, making it hard to test or reuse in other contexts (like a future web-triggered sync). The API was also insecure for health data.

**Solution:** 1. Extracted sync logic to a standalone SyncService (src/garsync/pipeline.py).
2. Simplified cli.py to just handle Typer inputs and orchestrate the service.
3. Added a simple FastAPI middleware for X-API-KEY validation.
4. Updated Astro frontend (Nano Stores + fetch) to include the header.
The result is a more modular backend and a secure-by-default API.

**Tags:** `#refactor` `#security` `#fastapi` `#cli`
