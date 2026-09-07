---
id: lesson-015-release-please-repo-setting-overrides-workflow-p
type: lesson
status: active
created: "2026-05-29"
recorded: "2026-03-01"
owner: manu
tags: [garsync, lesson, release-please, github-actions, permissions, gotcha]
---

# Release Please: Repo Setting Overrides Workflow Permissions

> Recorded 2026-03-01 in the flat `docs/lessons.md`; first appeared in git on 2026-05-29.

**Context:** Release Please CI failing with "not permitted to create or approve pull requests".

**Problem:** The workflow YAML already declared `permissions: pull-requests: write` and `contents: write`, but Release Please still couldn't create PRs. Debugging the YAML was a red herring.

**Solution:** Enable "Allow GitHub Actions to create and approve pull requests" in GitHub repo Settings → Actions → General → Workflow permissions. This is a repo-level toggle that overrides any workflow-level permission declaration.

**Why:** GitHub has a two-layer permission model: workflow YAML declares *what the token requests*, but the repo setting controls *what the repo allows*. The repo setting is the ceiling. See also: `pattern-release-please-ci.md` for the separate CI status check issue.

**Tags:** `#release-please` `#github-actions` `#permissions` `#gotcha`
