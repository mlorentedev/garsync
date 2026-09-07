---
id: lesson-008-e2e-integration-testing-pipeline-cli-db-api
type: lesson
status: active
created: "2026-05-29"
recorded: "2026-03-07"
owner: manu
tags: [garsync, lesson, testing, integration-tests, fastapi, cli]
---

# E2E Integration Testing Pipeline (CLI -> DB -> API)

> Recorded 2026-03-07 in the flat `docs/lessons.md`; first appeared in git on 2026-05-29.

**Context:** Finishing Sprint 4 (Integration + Deploy) for GarSync project.

**Problem:** Testing a full pipeline involving CLI, DB, and FastAPI requires a clean way to mock external APIs while ensuring real data persistence and retrieval works as expected.

**Solution:** Created a dedicated integration test (tests/test_integration_full.py) that:
1. Mocks the external API (GarminClient) using patch.
2. Uses CliRunner to execute the CLI sync command.
3. Points the CLI to a temporary SQLite file.
4. Initializes the FastAPI app (via factory) with a connection to the SAME SQLite file.
5. Uses httpx AsyncClient to verify that the data synced by the CLI is correctly exposed by the API.
This ensures the schema, repository, and API layers are perfectly aligned.

**Tags:** `#testing` `#integration-tests` `#fastapi` `#cli`
