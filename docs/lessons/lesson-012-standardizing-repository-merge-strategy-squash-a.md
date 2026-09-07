---
id: lesson-012-standardizing-repository-merge-strategy-squash-a
type: lesson
status: active
created: "2026-05-29"
recorded: "2026-03-07"
owner: manu
tags: [garsync, lesson, github, devops, git-workflow, release-please]
---

# Standardizing Repository Merge Strategy (Squash and Merge)

> Recorded 2026-03-07 in the flat `docs/lessons.md`; first appeared in git on 2026-05-29.

**Context:** Repository configuration for GarSync project.

**Problem:** Standardizing merge strategy to maintain a clean git history and ensure compatibility with automated release tools like release-please.

**Solution:** Configured GitHub repository settings via gh CLI:
- Enabled 'Squash and Merge' as the mandatory merge strategy.
- Disabled standard merge commits and rebase merges.
- Enabled automatic branch deletion after merge.
- Configured squash commit titles and messages to follow PR metadata.
This ensures every feature/fix results in a single, well-formatted commit on the master branch.

**Tags:** `#github` `#devops` `#git-workflow` `#release-please`
