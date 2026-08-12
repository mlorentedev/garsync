---
id: "garsync-lessons"
type: lesson
status: active
tags: [garsync, lessons]
created: "2026-02-28"
owner: manu
---

# GarSync: Lessons Learned

## L-001: Garmin API response format inconsistencies

- **Context:** `client.py` fetch methods
- **Finding:** Garmin API returns body battery as list of dicts sometimes, single dict others. HR data can have missing `restingHeartRate` key entirely.
- **Pattern:** Always use `.get()` with defaults, handle both list and dict formats, catch per-record parsing errors without blocking the full sync.

## L-002: Garmin API data availability gaps

- **Context:** Sprint 3 dashboard — discovered during data audit
- **Finding:** The `garminconnect` Python library returns null for: `hrv_balance`, `body_battery_highest`, `body_battery_lowest`, `stress_average`, and all sleep phase fields (`deep_sleep_seconds`, `light_sleep_seconds`, `rem_sleep_seconds`, `awake_sleep_seconds`, `sleep_score`). Only `resting_heart_rate` and activity data are consistently populated.
- **Impact:** Removed SleepChart, HRV KPI card, and Body Battery KPI from the dashboard. The schema and API endpoints remain (data might become available with a future library update).
- **Pattern:** Always audit real data in the DB before building UI components. Don't trust API schemas — verify field population with actual queries.

## L-003: Astro component error handling

- **Context:** Sprint 3 code review
- **Finding:** Bare `catch {}` blocks in Astro `<script>` tags swallow errors silently. Variable name collisions between `catch (err)` and DOM variables named `err` cause build failures in Astro/Vite.
- **Pattern:** Always use `catch (error) { console.error("[Component]", error); }` and name DOM error elements `errDiv` to avoid collisions with the catch variable.

### [2026-03-07] E2E Integration Testing Pipeline (CLI -> DB -> API)
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

### [2026-03-07] Decoupling Sync Logic and Securing Personal Health APIs
**Context:** Refactoring CLI and adding API Key security to GarSync.
**Problem:** CLI logic was tightly coupled with DB operations, making it hard to test or reuse in other contexts (like a future web-triggered sync). The API was also insecure for health data.
**Solution:** 1. Extracted sync logic to a standalone SyncService (src/garsync/pipeline.py).
2. Simplified cli.py to just handle Typer inputs and orchestrate the service.
3. Added a simple FastAPI middleware for X-API-KEY validation.
4. Updated Astro frontend (Nano Stores + fetch) to include the header.
The result is a more modular backend and a secure-by-default API.
**Tags:** `#refactor` `#security` `#fastapi` `#cli`

### [2026-03-07] Minimizing Authentication Overhead with Token Caching
**Context:** Implementing session token caching in GarminClient.
**Problem:** Frequent logins to Garmin Connect using email and password can lead to rate limiting or temporary account blocks. Re-authenticating on every sync is inefficient.
**Solution:** Modified GarminClient to support token-based authentication via garth. On first run, it authenticates with credentials and saves the session tokens to a JSON file. Subsequent runs use these tokens if they are valid, falling back to credentials only if necessary. This minimizes the risk of account blocks and speeds up the authentication step.
**Tags:** `#authentication` `#caching` `#garmin-api` `#performance`

### [2026-03-07] Reactive Dashboards: Loading States and Trend Analysis
**Context:** Improving UX in the Astro dashboard for GarSync.
**Problem:** Static charts and tables felt 'frozen' while waiting for API responses. KPI cards provided context but no sense of progress or regression over time.
**Solution:** 1. Implemented 'Skeletons' (loading placeholders) using Tailwind's animate-pulse. These are triggered on every data-store change before the fetch starts.
2. Added 'Trend Indicators' by performing two parallel API calls: one for the current range and one for the immediately preceding range of equal duration. 
3. Used semantic coloring for trends (e.g., lower Resting HR is good/green, while more Activities is good/green).
The dashboard now feels much more reactive and provides actionable insights (progress tracking).
**Tags:** `#ux` `#frontend` `#astro` `#data-visualization`

### [2026-03-07] Standardizing Repository Merge Strategy (Squash and Merge)
**Context:** Repository configuration for GarSync project.
**Problem:** Standardizing merge strategy to maintain a clean git history and ensure compatibility with automated release tools like release-please.
**Solution:** Configured GitHub repository settings via gh CLI:
- Enabled 'Squash and Merge' as the mandatory merge strategy.
- Disabled standard merge commits and rebase merges.
- Enabled automatic branch deletion after merge.
- Configured squash commit titles and messages to follow PR metadata.
This ensures every feature/fix results in a single, well-formatted commit on the master branch.
**Tags:** `#github` `#devops` `#git-workflow` `#release-please`

### [2026-03-07] Troubleshooting PyPI Trusted Publishing 'invalid-publisher' Error
**Context:** Deploying a Python package to PyPI using GitHub Actions and Trusted Publishing (OIDC).
**Problem:** The publish job failed with `Error: Trusted publishing exchange failure: Token request failed: the server refused the request for the following reasons: * invalid-publisher: valid token, but no corresponding publisher (Publisher with matching claims was not found)`.
**Solution:** 1. Add `permissions: id-token: write` and `contents: read` to the job.
2. Ensure the `environment: pypi` in the YAML matches the 'Environment' field in the PyPI Trusted Publisher settings.
3. Verify that the 'Workflow Name' in PyPI is just the filename (e.g., `release.yml`) and the 'Branch' matches the repository's default branch (e.g., `master`).
4. The repository name in PyPI should not include the owner (e.g., `garsync`, not `mlorentedev/garsync`).
**Tags:** `#pypi` `#github-actions` `#oidc` `#trusted-publishing` `#devops`

### [2026-03-01] Pytest `-q` Flag Suppresses the Summary Line
**Context:** Making `make check` output clean and minimal (one line per step).
**Problem:** Pytest with `-q` or `-qq` suppresses the "N passed in Xs" summary line entirely, making it impossible to extract a clean result via `tail -1` or `grep`. Three iterations were needed to find the right flag combination.
**Solution:** Use `pytest --no-header --tb=short -W ignore::DeprecationWarning 2>&1 | tail -1` — no `-q` flag. `--no-header` suppresses the session header while preserving the summary. `-W ignore::DeprecationWarning` silences pydantic utcnow() warnings at source. `2>&1 | tail -1` captures only the final summary line.
**Why:** `-q` is designed to reduce verbosity, but it removes the very line most useful for CI summaries. `--no-header` is the surgical flag that removes noise without killing signal.
**Tags:** `#pytest` `#makefile` `#ci-output` `#gotcha`

### [2026-03-01] Release Please: Repo Setting Overrides Workflow Permissions
**Context:** Release Please CI failing with "not permitted to create or approve pull requests".
**Problem:** The workflow YAML already declared `permissions: pull-requests: write` and `contents: write`, but Release Please still couldn't create PRs. Debugging the YAML was a red herring.
**Solution:** Enable "Allow GitHub Actions to create and approve pull requests" in GitHub repo Settings → Actions → General → Workflow permissions. This is a repo-level toggle that overrides any workflow-level permission declaration.
**Why:** GitHub has a two-layer permission model: workflow YAML declares *what the token requests*, but the repo setting controls *what the repo allows*. The repo setting is the ceiling. See also: `pattern-release-please-ci.md` for the separate CI status check issue.
**Tags:** `#release-please` `#github-actions` `#permissions` `#gotcha`

### [2026-03-01] Makefile Unification: 19 Targets → 8 Public Targets
**Context:** Developer experience improvement — too many inconsistent Makefile targets.
**Problem:** The Makefile had ~19 named targets with internal details (setup-python, setup-poetry, frontend-check, etc.) leaking into `make help`. Running the app required two terminals (API + frontend). Docker config was stale (Streamlit ENV vars, dead `ui` service).
**Solution:** Plan designed to: (1) reduce to 8 public targets: `setup`, `check`, `smoke`, `dev`, `sync`, `format`, `docker`, `clean`; (2) make FastAPI serve Astro static files so `make dev` is one command/one port; (3) upgrade Dockerfile to 3-stage build (Node → Python → runtime); (4) simplify docker-compose to single service.
**Why:** Fewer commands = lower cognitive overhead. Single-port dev = faster iteration. Stale Docker config was misleading for new contributors.
**Status:** Plan approved but NOT yet executed. Plan file: `.claude/plans/velvety-exploring-glade.md`.
**Tags:** `#makefile` `#dx` `#docker` `#refactor`

### [2026-03-01] UX Decision: Auto-fetch Data on Date Change
**Context:** Dashboard date range filtering UX.
**Problem:** User disliked having to run `make sync` or click buttons to load data. The mental model was: "I pick dates, data appears."
**Solution:** Date inputs should trigger data fetching reactively — no explicit sync action needed. Changing date range = automatic API call to load matching data.
**Why:** The sync-then-view model adds friction. For a personal dashboard, reactive data loading on date change is the expected UX. `make sync` remains for CLI-only bulk imports from Garmin Connect, but the dashboard should never require it.
**Tags:** `#ux` `#frontend` `#decision`

### [2026-08-12] Ruff 0.16.2 Upgrade: Cascading Lint Rules
**Context:** Dependabot PR #29 bumped ruff from 0.15.4 to 0.16.2, new rules flagged existing code across 10+ source files.
**Problem:** Each PR commit to fix the CI pushed a new set of ruff rules, requiring 4 separate fix commits: UP045 (Optional[X]→X|None), UP017 (timezone.utc→UTC), UP006/UP035 (List→list), B008 (Depends config), DTZ011/DTZ005/DTZ001 (timezone-aware datetimes), S110/BLE001 (try-except-pass), RUF022 (__all__ sort), RUF059 (unused unpacked), RUF100 (unused noqa).
**Solution:** Instead of fixing incrementally (each CI run reveals more rules), fix locally with the target ruff version: `pip install ruff==<version>` and run `ruff check --fix src/ tests/` to catch ALL new rules in one pass.
**Why:** The dependabot PR bumps ruff to the newest version, which introduces progressively stricter rules. Each CI run uncovers more rules, causing a multi-commit cascade. Fixing locally with the exact target version avoids this.
**Tags:** `#ruff` `#linting` `#ci` `#gotcha`
