---
id: adr-014-dependency-alert-policy
type: adr
status: accepted
owner: manu
date: "2026-09-25"
issue: "mlorentedev/garsync#80"
tags: [architecture, decision, security, dependencies, supply-chain, garsync]
created: "2026-09-25"
depends_on: [adr-007-purpose-built-single-user-platform, adr-011-deployment-topology]
---

# ADR-014: Dependency Alerts Are Triaged by Reachability, and a Major-Version Ignore Must State Its Trigger

## Status

Accepted — 2026-09-25, decided with the owner in this session (SEC-006, #80). It replaces the implicit
policy in `.github/dependabot.yml` and supersedes none of ADR-007…013.

## Date

2026-09-25

## Context

Two live configurations contradicted each other. `.github/dependabot.yml` **ignores** astro
major-version bumps, while SEC-005 (#64) asked for an `astro >= 7.1.0` migration to clear the
dependabot alerts. One of the two had to be wrong, and both were configured.

Measured on 2026-09-25 (`gh api repos/mlorentedev/garsync/dependabot/alerts?state=open`):

| Fact | Value |
|---|---|
| Open alerts | **10, all against `astro`** in `frontend/package-lock.json` |
| Severity spread | **1 critical, 2 high, 5 medium, 2 low** — the "3 high" figure in #64 (2026-09-07) is stale |
| The critical one | CVSS 9.8, GHSA-26w7-cxv4-gfx2 — libheif RCE *"when a malicious AVIF image is optimized"* through the default Sharp image service. Fix: astro **7.2.8**, "which requires Sharp 0.35.4" |
| The two high ones | CVE-2026-54299 host-header SSRF in **prerendered error pages** (fix 6.4.6); CVE-2026-50146 reflected XSS via an unescaped slot name **during SSR** (fix 6.3.3) |
| Highest fix floor | **astro ≥ 7.2.8** — two majors above the installed 5.18.2 |

Three further facts decide what that means here, and each was verified rather than assumed:

1. **Astro is a build-time tool in this repository, not a runtime.** The `Dockerfile` builds the site in a
   `node:22-slim` stage and copies `frontend/dist` into a Python runtime image; `astro.config.mjs` sets no
   `output` and no adapter; no astro process runs in production. Both high findings require SSR, and the
   critical one requires an untrusted image to reach the image service.
2. **Nothing here optimizes images.** `grep -rn "astro:assets|<Image|getImage" frontend/src` returns nothing,
   so the service the critical finding runs through is never invoked — in the build or anywhere else.
3. **The dependency-level risk behind the critical alert is already closed.** The lock installs
   `sharp@0.35.4` via the override added in PR #63 — the exact version the advisory names as the fix.
   Verified by consequence after `npm ci`: `sharp=0.35.4 vips=8.18.6 heif=1.23.2`. Dependabot files the
   alert against `astro` because astro's own range says `< 0.35.4`, but the installed library is the fixed one.

Why the bump cannot simply be taken, and why the ignore exists at all:

- **PR #66 (astro 5.18.2 → 7.2.8) and PR #70 (tailwindcss 3 → 4, typescript 6 → 7) are both red, and
  structurally so.** `npm ci` fails with `ERESOLVE` because `@astrojs/tailwind@6` peers
  `astro ^3.0.0 || ^4.0.0 || ^5.0.0` (measured in the #66 `frontend` job log, 2026-09-09). Neither PR can
  ever go green on its own.
- They are **the two halves of one migration**: astro 6 replaced `@astrojs/tailwind` with
  `@tailwindcss/vite`, so astro 7 requires the Tailwind v4 move. That intersection is exactly CHORE-003
  (#62) — the ticket the plan had marked *deprioritised*.
- Astro 7 itself is not exotic here: `docs-site/` already runs **astro 7.3.4** (Starlight, no Tailwind),
  so the risk is concentrated in the Tailwind integration, not the framework.

## Options Considered

1. **Pay the alerts down in this change** (delete the ignore, land the migration). Rejected — not on the
   merits of the alerts, but on scope: it is an astro 7 + Tailwind 4 + TypeScript 7 migration of the whole
   frontend, and burying a two-major migration inside a ticket about a config contradiction is how a
   refactor ends up unreviewed. It is taken as a decision instead, in item 6 below.
2. **Keep the ignore and leave it unexamined.** Rejected: that is today's state, and it is what let a
   critical alert coexist with a configuration that suppresses its fix, with nothing recording why.
3. **Triage by reachability in the deployed artifact, and require the ignore to state its trigger.**
   Chosen.

## Decision

1. **An alert is triaged by reachability in the deployed artifact, never by its severity label.** Severity
   is the input that decides *how fast to look*, not the answer. "Critical" plus "the vulnerable code is
   unreachable in what we deploy" is a documented disposition; "high" plus "reachable on every request" is
   not made acceptable by being one notch lower.
2. **`version-update:semver-major` may be ignored only where the file states, in place: (a) why the major
   cannot be taken now, (b) what is actually exposed while it is not, and (c) the trigger that reopens the
   decision.** An ignore without those three is a silenced alert, not a decision.
3. **Dependency-level risk is patched at the dependency level** (overrides) whenever the advisory names a
   fixed version of a library the framework merely pins — as `sharp` was in PR #63. Waiting for a framework
   major to carry a library patch is the slower road to the same place.
4. **Build-time-only tools are judged on the artifact, not the source tree** — and that judgement must be
   re-made whenever the artifact changes shape. Adopting an SSR adapter, `output: server`, or publishing a
   public build changes it immediately.
5. **The alerts stay visible.** The ignore suppresses a *pull request class*, never the alert list: the
   disposition of these ten is recorded here and in #64, which is closed with the reasoning rather than
   left open as a standing reproach.
6. **The astro 7 + Tailwind 4 + TypeScript 7 migration keeps an owner and is promoted to P1: CHORE-003
   (#62).** It absorbs the astro half of SEC-005 and stops being deprioritised, because it is now the only
   path to the framework-level fixes, not a nice-to-have upgrade.
7. **Reopen triggers for this ADR** — any one voids the reachability argument, and the ignore must then be
   deleted as part of the change that trips it:
   - the frontend adopts an SSR adapter or `output: server`;
   - astro's image service is used on anything not authored in this repository;
   - a public, unauthenticated build of the frontend is deployed;
   - the frontend moves to Tailwind v4 for any other reason — at which point the ignore has no remaining
     justification, since its sole cause was the Tailwind integration that blocks the major;
   - an advisory appears that is reachable in a *static* build (a build-time injection, for example).
8. **PRs #66 and #70 are closed as structurally unmergeable**, with a pointer to #62 — not because they are
   unimportant, but because each ships half of one migration and `npm ci` fails for both.

## Consequences

### Positive

- The contradiction is resolved in one direction, with the reasoning in the repo rather than in a session.
- A real library fix (`sharp` → 0.35.4) is in place and verifiable today, instead of pending on a framework
  migration.
- The migration that *is* needed has an owner, a priority and a named trigger set, so "later" now has a
  definition.

### Negative

- Ten alerts remain open on the default branch, and one of them is a critical. That is a deliberate state
  with a recorded argument, and it is the kind of state that goes stale — which is why item 7 exists and
  why #64 is closed *with* the reasoning rather than silently.
- The reachability argument is only as good as the last person who checked the Dockerfile: it is a claim
  about deployment shape, and deployment shape is a thing that changes.

### Neutral

- Nothing about the alerts is suppressed from the alert list; what is suppressed is dependabot's proposal to
  make the change, which is the exact proposal that cannot land green until #62 does.

## References

- Issues: **#80** (this decision), **#64** (SEC-005, closed with this reasoning), **#66** and **#70** (closed
  as structurally unmergeable), **#62** (CHORE-003, owns the migration), #78 (CI-002, added the docs-site PR
  build)
- Evidence: `gh api repos/mlorentedev/garsync/dependabot/alerts?state=open` (2026-09-25, 10 alerts — 1/2/5/2);
  the `frontend` job log of PR #66 (2026-09-09, `ERESOLVE` on `@astrojs/tailwind@6`); `npm ci` + `sharp.versions`
  (`0.35.4` / `vips 8.18.6` / `heif 1.23.2`); `docs-site/package-lock.json` (astro 7.3.4)
- Files: `.github/dependabot.yml`, `frontend/package.json`, `frontend/astro.config.mjs`, `Dockerfile`
- [`docs/architecture/ticket-plan.md`](../architecture/ticket-plan.md) §2 · SC-register: not scope-bearing
  (this is an engineering policy, not a product decision)
