---
id: lesson-023-grep-in-a-make-target-turns-a-failure-into-a-green-line
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, makefile, ci, gates, gotcha]
---

# A `grep` in a make target turns a failing check into a green line

- **Context:** CI-002, unifying `make check` with what CI runs. Re-reading the `frontend-check` target
  instead of trusting it.
- **Finding:** the target ended with
  `npx astro check 2>/dev/null | grep -oP '\d+ errors' || echo "0 errors"` — **two independent defects in
  one line.** The pattern expects the plural, so Astro's `1 error` never matches; and `|| echo` converts
  the failure into success. Measured by consequence: with a deliberate type error appended to
  `frontend/src/lib/format.ts`, `npx astro check` exited **1** and reported `1 error`, while
  `make frontend-check` printed `astro-check .... 0 errors` and exited **0**. `make check` — the gate the
  PR template and `AGENTS.md` tell everyone to trust — was green on TypeScript that does not compile.
- **Not the pipeline's fault:** this Makefile already sets `.SHELLFLAGS := -c -o pipefail`, and it works —
  a deliberately failing test makes `make test` and `make check` exit 2. The defect was the `||`, which
  catches pipefail's non-zero status and replaces it with a success. Worth knowing before "fixing" a
  pipeline that was never broken.
- **Pattern:** a check may pipe its output into a summariser, but **never into a fallback that reports
  success**. Print the tool's own summary and let its exit status decide, or fail the target explicitly.
  More generally: **verify a gate by consequence, not by reading it** — break the thing it guards and
  watch it fail, because a green line is the one output a broken gate also produces (same class as
  [lesson-022](lesson-022-acceptance-criterion-delegated-to-a-dependency.md)).

**Tags:** `#makefile` `#ci` `#gates` `#testing` `#gotcha`
