---
id: lesson-038-a-reviewer-claim-about-tool-behaviour-is-checked-against-the-lessons-first
type: lesson
status: active
created: "2026-10-06"
owner: manu
tags: [review, dependabot, process, gotcha]
related: [lesson-021-dependabot-ignore-cannot-suppress-a-security-update]
---

# Lesson 038 — A reviewer's claim about a tool's behaviour is checked against the repo's lessons before it is applied

**Context:** PR #133 added Dependabot ignores for the Tailwind v4 and TypeScript 7 majors. PR-Agent
flagged it as THEORETICAL, saying "ignore conditions are also applied to security-update pull
requests", so the stated reopen trigger might never fire. The finding was applied, and the merged
comment then said the ignore "may also suppress a security PR".

**Problem:** that is false, and this repository had already measured it. Lesson 021 records that
`update-types` affects version updates only, with PR #66 as the evidence (a security update opened
straight through an astro major ignore). The reviewer could not see the lesson. The implementer
could have, and did not look. The result was a merged comment that contradicted a recorded
measurement.

**Solution:** corrected in the crystallize pass that found it. The procedure from now on: before
applying a review finding that asserts how a tool behaves, `grep -ril <tool> docs/lessons docs/adr`.
If the repo has measured it, the measurement wins within the scope it covers (the same tool, contract and kind of update), and the triage reply cites it. Outside that scope it is a lead to re-measure, not a verdict. A THEORETICAL or
SPECULATIVE grade is a reason to verify, never a reason to comply. The same applies to the opposite case: the review of this lesson's own PR corrected lesson 037's mechanism (binary store, not JSON), and was right, which a dummy-file measurement confirmed before it was applied.

**Why:** applying every finding feels like diligence, and the triage looks complete. But a reviewer
works from its general knowledge of the tool, while the repo has measured this case. When the two
disagree, the measurement is the stronger evidence.
