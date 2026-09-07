---
id: lesson-016-makefile-unification-19-targets-8-public-targets
type: lesson
status: active
created: "2026-05-29"
recorded: "2026-03-01"
owner: manu
tags: [garsync, lesson, makefile, dx, docker, refactor]
---

# Makefile Unification: 19 Targets → 8 Public Targets

> Recorded 2026-03-01 in the flat `docs/lessons.md`; first appeared in git on 2026-05-29.

**Context:** Developer experience improvement — too many inconsistent Makefile targets.

**Problem:** The Makefile had ~19 named targets with internal details (setup-python, setup-poetry, frontend-check, etc.) leaking into `make help`. Running the app required two terminals (API + frontend). Docker config was stale (Streamlit ENV vars, dead `ui` service).

**Solution:** Plan designed to: (1) reduce to 8 public targets: `setup`, `check`, `smoke`, `dev`, `sync`, `format`, `docker`, `clean`; (2) make FastAPI serve Astro static files so `make dev` is one command/one port; (3) upgrade Dockerfile to 3-stage build (Node → Python → runtime); (4) simplify docker-compose to single service.

**Why:** Fewer commands = lower cognitive overhead. Single-port dev = faster iteration. Stale Docker config was misleading for new contributors.

**Status:** Items (3) and (4) landed (3-stage Dockerfile, single-service compose). Items (1) and (2) are still open: `make help` advertises a `docker` target that does not exist and `dev` still starts two servers. The original plan file (`.claude/plans/velvety-exploring-glade.md`) was in the gitignored `.claude/` directory and is gone; the work is tracked in [CHORE-002 (#57)](https://github.com/mlorentedev/garsync/issues/57).

**Tags:** `#makefile` `#dx` `#docker` `#refactor`
