---
id: garsync-lessons-index
type: index
status: active
created: "2026-09-06"
owner: manu
tags: [garsync, lessons, index]
---

# Lessons Learned Index

One file per lesson. `created` is the date the entry first appeared in git; entries migrated from the flat `docs/lessons.md` also carry the date they were originally recorded.

| # | Date | Title | File | Tags |
|---|---|---|---|---|
| 001 | 2026-05-29 | Garmin API response format inconsistencies | [lesson-001-garmin-api-response-format-inconsistencies.md](lesson-001-garmin-api-response-format-inconsistencies.md) | `garmin-api`, `client` |
| 002 | 2026-05-29 | Garmin API data availability gaps | [lesson-002-garmin-api-data-availability-gaps.md](lesson-002-garmin-api-data-availability-gaps.md) | `garmin-api`, `data-audit`, `dashboard` |
| 003 | 2026-05-29 | Astro component error handling | [lesson-003-astro-component-error-handling.md](lesson-003-astro-component-error-handling.md) | `astro`, `error-handling` |
| 004 | 2026-09-05 | `sops --rotate -i` MERGES recipients instead of replacing them | [lesson-004-sops-rotate-i-merges-recipients-instead-of-repla.md](lesson-004-sops-rotate-i-merges-recipients-instead-of-repla.md) | `sops`, `age`, `secrets` |
| 005 | 2026-09-05 | Env vars are captured at `create_app()` time | [lesson-005-env-vars-are-captured-at-create-app-time.md](lesson-005-env-vars-are-captured-at-create-app-time.md) | `testing`, `env`, `fastapi` |
| 006 | 2026-09-05 | httpx never sends `Secure` cookies over `http://` | [lesson-006-httpx-never-sends-secure-cookies-over-http.md](lesson-006-httpx-never-sends-secure-cookies-over-http.md) | `testing`, `httpx`, `cookies` |
| 007 | 2026-09-05 | `import datetime` + `from datetime import datetime` shadowing breaks PEP 604 unions at import time | [lesson-007-import-datetime-from-datetime-import-datetime-sh.md](lesson-007-import-datetime-from-datetime-import-datetime-sh.md) | `python`, `datetime`, `typing` |
| 008 | 2026-05-29 | E2E Integration Testing Pipeline (CLI -> DB -> API) | [lesson-008-e2e-integration-testing-pipeline-cli-db-api.md](lesson-008-e2e-integration-testing-pipeline-cli-db-api.md) | `testing`, `integration-tests`, `fastapi`, `cli` |
| 009 | 2026-05-29 | Decoupling Sync Logic and Securing Personal Health APIs | [lesson-009-decoupling-sync-logic-and-securing-personal-heal.md](lesson-009-decoupling-sync-logic-and-securing-personal-heal.md) | `refactor`, `security`, `fastapi`, `cli` |
| 010 | 2026-05-29 | Minimizing Authentication Overhead with Token Caching | [lesson-010-minimizing-authentication-overhead-with-token-ca.md](lesson-010-minimizing-authentication-overhead-with-token-ca.md) | `authentication`, `caching`, `garmin-api`, `performance` |
| 011 | 2026-05-29 | Reactive Dashboards: Loading States and Trend Analysis | [lesson-011-reactive-dashboards-loading-states-and-trend-ana.md](lesson-011-reactive-dashboards-loading-states-and-trend-ana.md) | `ux`, `frontend`, `astro`, `data-visualization` |
| 012 | 2026-05-29 | Standardizing Repository Merge Strategy (Squash and Merge) | [lesson-012-standardizing-repository-merge-strategy-squash-a.md](lesson-012-standardizing-repository-merge-strategy-squash-a.md) | `github`, `devops`, `git-workflow`, `release-please` |
| 013 | 2026-05-29 | Troubleshooting PyPI Trusted Publishing 'invalid-publisher' Error | [lesson-013-troubleshooting-pypi-trusted-publishing-invalid.md](lesson-013-troubleshooting-pypi-trusted-publishing-invalid.md) | `pypi`, `github-actions`, `oidc`, `trusted-publishing`, `devops` |
| 014 | 2026-05-29 | Pytest `-q` Flag Suppresses the Summary Line | [lesson-014-pytest-q-flag-suppresses-the-summary-line.md](lesson-014-pytest-q-flag-suppresses-the-summary-line.md) | `pytest`, `makefile`, `ci-output`, `gotcha` |
| 015 | 2026-05-29 | Release Please: Repo Setting Overrides Workflow Permissions | [lesson-015-release-please-repo-setting-overrides-workflow-p.md](lesson-015-release-please-repo-setting-overrides-workflow-p.md) | `release-please`, `github-actions`, `permissions`, `gotcha` |
| 016 | 2026-05-29 | Makefile Unification: 19 Targets → 8 Public Targets | [lesson-016-makefile-unification-19-targets-8-public-targets.md](lesson-016-makefile-unification-19-targets-8-public-targets.md) | `makefile`, `dx`, `docker`, `refactor` |
| 017 | 2026-05-29 | UX Decision: Auto-fetch Data on Date Change | [lesson-017-ux-decision-auto-fetch-data-on-date-change.md](lesson-017-ux-decision-auto-fetch-data-on-date-change.md) | `ux`, `frontend`, `decision` |
| 018 | 2026-08-11 | Ruff 0.16.2 Upgrade: Cascading Lint Rules | [lesson-018-ruff-0-16-2-upgrade-cascading-lint-rules.md](lesson-018-ruff-0-16-2-upgrade-cascading-lint-rules.md) | `ruff`, `linting`, `ci`, `gotcha` |
| 019 | 2026-09-07 | Dependabot Group Can Smuggle Major Bumps — Red CI | [lesson-019-dependabot-group-can-smuggle-major-bumps-red-ci.md](lesson-019-dependabot-group-can-smuggle-major-bumps-red-ci.md) | `dependabot`, `npm`, `peer-deps`, `ci`, `gotcha` |
| 020 | 2026-09-07 | npm Scoped Overrides Apply to the Whole Subtree | [lesson-020-npm-scoped-overrides-apply-to-whole-subtree.md](lesson-020-npm-scoped-overrides-apply-to-whole-subtree.md) | `npm`, `overrides`, `security`, `dependabot`, `gotcha` |
