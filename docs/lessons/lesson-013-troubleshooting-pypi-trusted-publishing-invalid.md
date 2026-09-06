---
id: lesson-013-troubleshooting-pypi-trusted-publishing-invalid
type: lesson
status: active
created: "2026-05-29"
recorded: "2026-03-07"
owner: manu
tags: [garsync, lesson, pypi, github-actions, oidc, trusted-publishing, devops]
---

# Troubleshooting PyPI Trusted Publishing 'invalid-publisher' Error

> Recorded 2026-03-07 in the flat `docs/lessons.md`; first appeared in git on 2026-05-29.

**Context:** Deploying a Python package to PyPI using GitHub Actions and Trusted Publishing (OIDC).

**Problem:** The publish job failed with `Error: Trusted publishing exchange failure: Token request failed: the server refused the request for the following reasons: * invalid-publisher: valid token, but no corresponding publisher (Publisher with matching claims was not found)`.

**Solution:** 1. Add `permissions: id-token: write` and `contents: read` to the job.
2. Ensure the `environment: pypi` in the YAML matches the 'Environment' field in the PyPI Trusted Publisher settings.
3. Verify that the 'Workflow Name' in PyPI is just the filename (e.g., `release.yml`) and the 'Branch' matches the repository's default branch (e.g., `master`).
4. The repository name in PyPI should not include the owner (e.g., `garsync`, not `mlorentedev/garsync`).

**Tags:** `#pypi` `#github-actions` `#oidc` `#trusted-publishing` `#devops`
