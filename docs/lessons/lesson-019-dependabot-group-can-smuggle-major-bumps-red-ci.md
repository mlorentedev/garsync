# Lesson-019: A grouped dependabot update can smuggle major bumps — red CI on a bump-only change

- **Context:** dependabot PR #54 (2026-09-07) grouped `nanostores` (minor), `tailwindcss` 3→4 and `typescript` 6→7 in one update. CI's frontend job failed at `npm ci` with `ERESOLVE`: `@astrojs/check@0.9.10` declares peer `typescript@^5.0.0 || ^6.0.0`, so TypeScript 7 (the Go port) cannot resolve.
- **Finding:** The red test was not a code bug — it was a peer-dependency conflict inside a "bump" PR, and the repo's dependabot policy (minor+patch only) had been silently bypassed by grouping. The other major in the group (`tailwindcss` v4, breaking: CSS-first config, `@astrojs/tailwind` unsupported) was not even install-breaking, just unrunnable.
- **Pattern:** Diagnose grouped dependabot reds from the `npm ci` log first (`ERESOLVE` names the offending peer chain). Fix on the PR branch by keeping the safe bumps, reverting the majors to the master ranges, and regenerating the lockfile; file the majors on the board for a real migration (CHORE-003) instead of force-bumping through.
- **Refs:** CHORE-003 (mlorentedev/garsync#62), PR #54 merged as `9a409f9`.
