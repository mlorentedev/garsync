---
id: lesson-021-dependabot-ignore-cannot-suppress-a-security-update
type: lesson
status: active
created: "2026-09-24"
owner: manu
tags: [dependabot, security, npm, ci, gotcha]
related: [lesson-019-dependabot-group-can-smuggle-major-bumps-red-ci]
---

# Lesson 021 — A Dependabot `update-types` ignore cannot suppress a security update

## Context

`.github/dependabot.yml` carries two rules that look like they should keep Astro on 5.x:

```yaml
    groups:
      npm_and_yarn:
        patterns: ["*"]
        exclude-patterns: ["astro"]
    ignore:
      - dependency-name: "astro"
        update-types: ["version-update:semver-major"]
```

Those rules were added on 2026-08-10 (`a513d7e`). PR #66, which bumps `astro` from `5.18.2` to
`7.2.8`, was opened on 2026-09-09 — **after** them. The first instinct is that the ignore is
misconfigured.

## What is actually true

It is not misconfigured; it is being asked for something it cannot do. GitHub's Dependabot options
reference states that **`update-types` only affects *version* updates, not *security* updates**.
PR #66 is a security update for the advisories tracked in #64 (three high-severity, fixed in Astro
>= 7.1.0), so no `update-types` rule can suppress it and no `exclude-patterns` entry applies to it.

The consequence is a configuration that reads as a policy and behaves as nothing on the update path
that matters most. The repository ends up with an open PR it believes it forbade, and with three
advisories that stay open as long as the major is deferred — which is a *decision*, not an accident,
and nothing in the file says so.

## Why it matters here

Two failure modes follow, and both were live in this repository at once:

1. **A forbidden PR looks like a bot misbehaving.** Time goes into asking why Dependabot ignored the
   config, when the answer is documented behaviour.
2. **A red PR looks like a fixable install problem.** It is not: `npm ci` fails because
   `@astrojs/tailwind@6.0.2` peer-requires `astro@^3 || ^4 || ^5`. The major cannot be taken alone —
   the Astro 5 -> 7 migration drags the Tailwind integration, and Tailwind 4 changes the
   configuration model. That is a migration with a spec, not a bot-sized change.

`update-types` ignoring security updates also interacts with the sibling lesson: lesson 019 records a
Dependabot *group* smuggling major bumps into a green-looking PR. This one is the mirror image — a
*security* update arriving where the config meant to say "not yet".

## What to do instead

- **Treat a security-driven major as a decision, and write the decision where the config lives.** If
  the major is deferred, say so in `dependabot.yml` next to the ignore, with the advisories it leaves
  open — which turns a silent policy into a recorded trade-off (ticket SEC-006).
- **Check whether Dependabot's own tooltip says "security update"** before concluding an ignore rule
  failed. `gh pr view <n> --json labels` shows a `dependencies` label either way, so read the PR body
  or the alert list instead.
- **Keep the group's `exclude-patterns` for the majors being deferred** (lesson 019) *and* remember
  they do not bind the security path — the two rules cover different update types, and neither one
  covers both.

## Evidence

- PR #66, opened 2026-09-09 over `dependabot/npm_and_yarn/frontend/astro-7.2.8`.
- Local reproduction: `npm ci --dry-run` on that branch fails with `peer astro@"^3.0.0 || ^4.0.0 || ^5.0.0" from @astrojs/tailwind@6.0.2`.
- GitHub, *Dependabot options reference*: "`update-types` only affects version updates, not security updates" (accessed 2026-09-24).
- Related: lesson 019 (group smuggling majors), issue #64 SEC-005, issue #80 SEC-006.
