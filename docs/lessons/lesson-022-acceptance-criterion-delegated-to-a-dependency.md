---
id: lesson-022-acceptance-criterion-delegated-to-a-dependency
type: lesson
status: active
created: "2026-09-05"
owner: manu
tags: [garsync, lesson, testing, cors, dependencies, security]
---

# An acceptance criterion backed only by a dependency's behaviour is not enforced

- **Context:** SEC-001 review (PR #44). AC5 stated "wildcard origin is never honored with credentials". The implementation passed `GARSYNC_ALLOWED_ORIGINS` straight to Starlette's `CORSMiddleware` and relied on Starlette refusing `*` together with `allow_credentials=True`.
- **Finding:** That guarantee lives in a specific Starlette version, not in GarSync. CodeRabbit flagged it as a Major finding: a dependency bump could silently reopen the hole while every test stayed green, because no test asserted the property itself.
- **Pattern:** When an AC says "X must never happen", make the application fail closed on X (here `create_app()` raises `ValueError` if `*` appears in `GARSYNC_ALLOWED_ORIGINS`) and pin it with a regression test (`tests/api/test_cors.py::test_cors_wildcard_origin_is_rejected_at_startup`). A property delegated to a library is a hope, not a control.

**Tags:** `#testing` `#cors` `#dependencies` `#security` `#gotcha`
