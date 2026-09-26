---
id: lesson-035-an-empty-list-is-a-claim-about-the-body
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, api-design, queries, ingestion, failure-modes]
---

# An empty list is a claim about the data, so refusing is sometimes the only honest answer

SC-02(3) asks the system to tell *"not uploaded yet"* apart from *"no data"*, because the FitDays scale
may sync hours late and Garmin rewrites sleep and training-readiness through the morning — and a staleness
alert that cannot tell those apart pages on a holiday. Writing the queries (`SUB-002` block 6) surfaced a
third state the register does not name, and the one that breaks an alert.

## The three states, and why two of them cannot share an answer

| Day D | Evidence | Sentence the digest may print |
|---|---|---|
| inside a covered window, every covering run fetched 0 rows, no class row | `ingest_run` | not uploaded yet — expected, late |
| inside a covered window, a covering run fetched rows, no row for D | `ingest_run` + class table | no data for D — a rest day, a watch left on the charger |
| outside every covered window | **nothing** | never asked — a bug in the runner, or a class with no fetch yet |

The third is the dangerous one, because the natural implementation of "which days do we have?" over the
first two answers is a function that returns `[]` when it has nothing to say. For `activities` — minute
resolved, `limit`-fetched, no cursor until SUB-003 — an empty list means *"we asked about every day and
found nothing"*. That is a claim about the body, produced by a fact about the code, and it is
indistinguishable from a genuine rest day by anyone downstream.

So `days_not_uploaded_yet` / `days_with_no_data` **raise** for `activities` ("not window-complete until
SUB-003"), for `stress` (windowed, no storage yet), and for an unknown class name. `covered_days` is the
one function that may answer `set()` truthfully — "no window covers this range" is exactly the third
state, and the caller is expected to compare it against the range it asked about.

The empty answer and the refusal differ in one respect worth naming: the empty answer is *checked* data,
the refusal is *unchecked*. Anything that turns a refusal into an empty list to keep a caller happy has
converted "we do not know" into "there is nothing", which is the failure mode this whole spec exists to
kill (AC7's `rows_upserted` lying in exactly that direction).

## The other half of the block: a guard must be able to fail

AC8 is a lexical guard — every occurrence of `updated_at` in `src/` must be a write. Two things made it
worth committing:

- **The exemption is by syntax, not by line.** Docstrings and comments are collected from the AST and the
  token stream; every other mention is code or SQL. A line-based exemption ("skip lines that look like
  prose") would let a read hide under a docstring that shares the line. There is a test for exactly that,
  and it fails if the exemption is widened to the line.
- **The guard's own discriminating power is table-tested**, seven reads against eight writes. A guard
  that passes on a clean tree proves nothing about being clean — that is lesson 034's shape again, one
  level up: the risk in a guard is not that it fails, it is that it can never fail.

The strictness is deliberate and slightly inconvenient: a `SELECT updated_at` that only wanted to
*display* the value also fails. That is the trade — a display is one refactor away from a predicate, and
the cheap fix for the refactor is to read the column.

## Related

- `lesson-034-a-passing-verification-command-can-still-prove-nothing.md` — the same posture applied to
  the spec's own verifiers.
- `docs/adr/adr-008-ingestion-ledger-and-adapters.md` §5, §13 — why a window is re-covered, and where the
  per-class coverage policy lives.
- `specs/SUB-002/verification.md`, decisions 16–17.
