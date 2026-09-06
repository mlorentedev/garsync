---
id: lesson-005-env-vars-are-captured-at-create-app-time
type: lesson
status: active
created: "2026-09-05"
owner: manu
tags: [garsync, lesson, testing, env, fastapi]
---

# Env vars are captured at `create_app()` time

- **Context:** SEC-001 auth tests
- **Finding:** The auth config (`GARSYNC_API_KEY`, `GARSYNC_ACCESS_PASSWORD`) is read inside `create_app()`. A test that calls `monkeypatch.setenv()` AFTER the factory call silently tests stale config (bit us: integration test set env after `create_app` and failed with 403).
- **Pattern:** Pin env vars BEFORE building the app in any test.

**Tags:** `#testing` `#env` `#fastapi`
