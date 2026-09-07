---
id: lesson-018-ruff-0-16-2-upgrade-cascading-lint-rules
type: lesson
status: active
created: "2026-08-11"
recorded: "2026-08-12"
owner: manu
tags: [garsync, lesson, ruff, linting, ci, gotcha]
---

# Ruff 0.16.2 Upgrade: Cascading Lint Rules

> Recorded 2026-08-12 in the flat `docs/lessons.md`; first appeared in git on 2026-08-11.

**Context:** Dependabot PR #29 bumped ruff from 0.15.4 to 0.16.2, new rules flagged existing code across 10+ source files.

**Problem:** Each PR commit to fix the CI pushed a new set of ruff rules, requiring 4 separate fix commits: UP045 (Optional[X]→X|None), UP017 (timezone.utc→UTC), UP006/UP035 (List→list), B008 (Depends config), DTZ011/DTZ005/DTZ001 (timezone-aware datetimes), S110/BLE001 (try-except-pass), RUF022 (__all__ sort), RUF059 (unused unpacked), RUF100 (unused noqa).

**Solution:** Instead of fixing incrementally (each CI run reveals more rules), fix locally with the target ruff version: `pip install ruff==<version>` and run `ruff check --fix src/ tests/` to catch ALL new rules in one pass.

**Why:** The dependabot PR bumps ruff to the newest version, which introduces progressively stricter rules. Each CI run uncovers more rules, causing a multi-commit cascade. Fixing locally with the exact target version avoids this.

**Tags:** `#ruff` `#linting` `#ci` `#gotcha`
