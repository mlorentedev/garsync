---
id: lesson-014-pytest-q-flag-suppresses-the-summary-line
type: lesson
status: active
created: "2026-05-29"
recorded: "2026-03-01"
owner: manu
tags: [garsync, lesson, pytest, makefile, ci-output, gotcha]
---

# Pytest `-q` Flag Suppresses the Summary Line

> Recorded 2026-03-01 in the flat `docs/lessons.md`; first appeared in git on 2026-05-29.

**Context:** Making `make check` output clean and minimal (one line per step).

**Problem:** Pytest with `-q` or `-qq` suppresses the "N passed in Xs" summary line entirely, making it impossible to extract a clean result via `tail -1` or `grep`. Three iterations were needed to find the right flag combination.

**Solution:** Use `pytest --no-header --tb=short -W ignore::DeprecationWarning 2>&1 | tail -1` — no `-q` flag. `--no-header` suppresses the session header while preserving the summary. `-W ignore::DeprecationWarning` silences pydantic utcnow() warnings at source. `2>&1 | tail -1` captures only the final summary line.

**Why:** `-q` is designed to reduce verbosity, but it removes the very line most useful for CI summaries. `--no-header` is the surgical flag that removes noise without killing signal.

**Tags:** `#pytest` `#makefile` `#ci-output` `#gotcha`
