---
id: lesson-034-a-passing-verification-command-can-still-prove-nothing
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, testing, spec-driven-development, verification, tooling]
---

# A passing verification command can still prove nothing

`specs/SUB-002/features.json` is the change's executable contract: twelve entries, each with a
`verification` command and a `state`. Before closing block 5 I ran them — and the run produced three
defects, only one of which was in the code.

## 1. Paraphrasing the contract produces fake failures

I typed the twelve commands from memory into a throwaway script instead of reading them out of the
file. Two exited `4` (pytest usage error) against a filename that exists nowhere:
`tests/test_ledger_counts.py`. It was my invention — the real cases are
`tests/test_idempotency.py::TestLedgerCounts` — and read as a spec defect it would have "fixed" a
contract that was sound.

**A contract is read, not retyped.** The file is the SSOT; the moment the commands are reconstructed
from recollection, you are testing your memory of the spec instead of the spec.

## 2. Running it verbatim found the real one

`SUB-002-f12` is AC12 — "the migration is additive and idempotent". Its command:

```
poetry run pytest tests/test_migrations.py -q -k 'Revision0003 or upgrading_twice'
```

Exit code: **0**. Selected cases: **one** — `test_upgrading_twice_changes_nothing`, which was written
for `0002` and knows nothing about `0003`. `grep -n "0003\|rows_fetched" tests/test_migrations.py` returns
nothing: no test asserts that the new revision adds two columns, creates no table, or leaves a v2
database schema-identical to one built from a v1 fixture. The only evidence for AC12 was a rehearsal I
ran by hand on a copy of the real database, which is proof of *that file's* state, not a guard.

So the entry could be marked `verified` on a green exit and the spec would archive with its migration
claim unguarded — the same shape as lesson 032's ratchet: **the mechanism reports success because nobody
asked it what it actually looked at.**

## 3. The rule that came out of it

- Record, beside each command's exit code, **what it selected**: case count and the names. A zero-exit
  command that selects one case is not a verified criterion, it is a smoke test.
- The selected set must **name the thing the criterion names**. `AC12` says `0003`; a command whose
  filter matches no test containing `0003` is vacuous regardless of its colour.
- A criterion whose evidence is a hand-run rehearsal is *evidence in prose*, not a guard. Block 7 writes
  the test (`0003` adds exactly two columns and no table; fresh-v2 and migrated-v1 fixtures are
  schema-identical; re-running changes nothing) and only then may `f12` read `verified`.
- When a sweep fails, check the **command's provenance** before "fixing" the artifact it points at.

## Related

- `lesson-032-a-coverage-ratchet-raised-in-the-closing-block-is-a-ratchet-that-lags.md` — a gate that
  passes because it measures a stale number.
- `specs/SUB-002/verification.md`, "Vacuous criteria, caught before they could mislead" — four criteria
  in this spec were unrunnable as scaffolded; the class is recurring, not incidental.
