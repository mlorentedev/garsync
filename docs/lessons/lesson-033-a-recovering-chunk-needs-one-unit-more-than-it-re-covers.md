---
id: lesson-033-a-recovering-chunk-needs-one-unit-more-than-it-re-covers
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, ingestion, cursors, windowing, arithmetic, gotcha]
---

# A re-covering chunk needs one unit more than it re-covers

Found by driving the window rule from a real run (`specs/SUB-002`, the per-class run). The window
arithmetic had been green, 100% covered, for four commits — and it contained a case where the ingest
pipeline stops working forever.

## The stall

The coverage window is `start = min(last_cursor, floor)` and `end_effective = min(end, start + trailing)`,
with `covered_through = end_effective − 1 unit`. Starting *at* the cursor is deliberate: re-covering the
cursor's own unit is how a morning revision lands (ADR-008 §5, and `resolve_window`'s own decision 2 in
this spec).

Feed it a one-day trailing floor and a cursor four days old:

```
cursor          = 2026-03-01
now             = 2026-03-05 12:00Z (Europe/Madrid)   → end = 03-06, floor = 03-05
start           = min(03-01, 03-05)                   = 03-01
end_effective   = min(03-06, 03-01 + 1 day)           = 03-02
covered_through = 03-02 − 1 day                       = 03-01     ← the cursor, unchanged
```

Every subsequent run computes the same window: it fetches one day, writes a `success` row, advances the
watermark by **zero**, and looks healthy. The gap closes at 0 days per run. Generalised: a chunk that
begins at the watermark makes `trailing − 1` units of progress, so at `trailing = 1` it makes none.

## Why nothing caught it

- **The constant was the shield.** Before the run existed, `trailing_days` had exactly one value — 13
  units of progress per chunk. The degenerate input was unreachable. Making the floor caller-supplied
  (`--days N`, so the caller can ask for one day) is what put `N = 1` on the table: **parameterising a
  constant is a contract change, not a refactor**, and it inherits the need for a bound.
- **The existing invariant test asserted the right property at the only value the floor could then
  take.** `test_a_long_gap_is_closed_in_chunks_without_a_hole` already loops and already asserts
  `covered_through > cursor` — at 14, because that was a module constant, not an input. A property
  measured at one input is not a property of the function; the guard now runs the same loop over
  `{1, 2, 3, 14}`, which is what makes the class of bug unreachable rather than unobserved.
- **The failure mode is silent by construction.** No exception, no error row, no rollback: an
  idempotent upsert of data already held, and a ledger row that keeps claiming the same coverage. The
  only observable is the absence of movement, which is exactly what a rest day looks like.

## The fix, and the invariant that keeps it

`MIN_CHUNK_UNITS = 2`, applied in `_chunk_units()` — one function both granularities call, so the day
window and the minute window cannot drift. Two units is the minimum that makes progress: the seam plus
one new day. The ratified 14-day budget is untouched (`max(14, 2) == 14`), so the ≈71-calls-per-run
arithmetic keeps its meaning.

The property is now asserted three times, at the levels that can each fail alone:

- `test_every_floor_value_closes_the_gap_without_stalling` — the convergence loop over
  `{1, 2, 3, 14}`, so no floor value can reintroduce the stall;
- `test_a_one_unit_floor_could_otherwise_stall_forever` — `covered_through > cursor` for the arithmetic
  at the degenerate input, with the exact day list pinned;
- `TestRunCursors::test_a_second_run_over_an_unchanged_window_claims_coverage_without_claiming_changes`
  — the same fact through a real run pair, where the interesting half is that it advances coverage
  while `rows_upserted` reads 0.

## Related

- `lesson-028-a-begin-the-repositories-can-commit-through-is-not-a-transaction-boundary.md` — the same
  shape: a mechanism that satisfies its own description and not its purpose.
- `docs/adr/adr-008-ingestion-ledger-and-adapters.md` — §5's re-cover rule is what makes the seam cost
  a unit; this lesson is its arithmetic consequence.
