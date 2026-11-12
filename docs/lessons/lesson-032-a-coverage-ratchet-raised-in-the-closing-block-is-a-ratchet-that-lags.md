---
id: lesson-032-a-coverage-ratchet-raised-in-the-closing-block-is-a-ratchet-that-lags
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, coverage, ci, testing, gotcha]
---

# A coverage ratchet raised in the closing block is a ratchet that lags

Found while writing SUB-002's ledger counts, and it is a process defect, not a code one.

The rule is in `.coverage-baseline` itself: *"add the tests that close the gap, then move the number in
the same commit."* The task list for the same change put that tick in **block 7 — Gate and closure**:

> `- [ ] [AC10] make check green …; raise .coverage-baseline only if the new tests lift it, in the same
> commit that pays for it`

Those two instructions are not compatible, and the file lost the argument.

- **Measured.** Blocks 2–3 (`transaction()`, the guarded upserts) took the tree from **85.17 → 85.67**
  (1005 statements, 144 missed) and block 4 (`0003_ledger_counts`, `TestLedgerCounts`) to **85.88**
  (1020 statements, 144 missed). The recorded baseline stayed **85.17** for all three commits, because
  the tick that moves it had not been reached yet.
- **Why a lag is not a harmless under-claim.** `scripts/check-coverage.sh` fails the run at
  `baseline − 2`. With the baseline 0.71 points behind the tree, the floor sat at **83.17** while the
  suite measured 85.88 — so a commit that deleted **2.71 points** of coverage still went green. The
  ratchet's whole value is monotonicity ("the baseline can only be raised deliberately"); a lagging
  baseline silently converts a floor into headroom, and the CI that enforces it reports *success* while
  doing so.
- **The mechanism that made it invisible.** Nothing in the gate compares the recorded number with the
  measured one. `check-coverage.sh` only asks "did we fall below the floor", never "is the floor where
  the tree actually is". A ratchet with no upper check drifts downward the moment the raise-step is
  deferred, and it drifts in the direction that stops protecting anything.

## The fix

1. **Move the number in the commit whose tests pay for it** — the rule as written. It was honoured on
   84.07 → 85.17 (window tests) and 85.17 → 85.88 (ledger counts), and skipped in between, which is
   exactly the interval the drift accumulated in.
2. **Reword the closing-block tick** (done in `specs/SUB-002/tasks.md`, same commit as this lesson).
   Raising is a per-commit act; what belongs in the closing block is *"`.coverage-baseline` equals what
   the tree measures"* — an assertion, not an action. The old wording made the raise a closure task, and
   that is where the drift came from.
3. Generalises beyond coverage: any gate of the form *fail if worse than the recorded value* needs its
   record updated **by the change that improves it**, not by a later cleanup. The same shape is what
   makes a mutation-testing threshold, a bundle-size budget, or a p95 latency SLO stop defending the
   property it names.

## Related

- `lesson-029-a-pragma-you-did-not-set-may-already-be-set-by-the-driver.md` — the sibling failure mode:
  an implicit value that disagrees with the explicit one, discovered by measuring rather than reading.
- `docs/adr/adr-008-ingestion-ledger-and-adapters.md` — the ledger this block was counting for.
