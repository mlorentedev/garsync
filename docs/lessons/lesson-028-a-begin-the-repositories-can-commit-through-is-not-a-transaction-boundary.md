---
id: lesson-028-a-begin-the-repositories-can-commit-through-is-not-a-transaction-boundary
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, sqlite, transactions, atomicity, ingestion, gotcha]
---

# A `BEGIN` the repositories can commit through is not a transaction boundary

Measured while implementing `specs/SUB-002` (the ingest ledger), on Python 3.13 / SQLite 3.46.

- **Finding.** Take the transaction away from the driver — `sqlite3.connect(path, isolation_level=None)`
  — and open it by hand, `BEGIN IMMEDIATE`. That is the right move (lesson 027), and on its own it does
  **not** give you one transaction per run, because every existing write helper still commits per row:

  ```
  w = sqlite3.connect(p, isolation_level=None)
  w.execute("BEGIN IMMEDIATE"); w.in_transaction        # True
  w.execute("INSERT INTO t(v) VALUES('x')")
  w.commit()                                            # what repo.upsert() does per row
  w.in_transaction                                      # False  ← the run's transaction is gone
  ```

  The row is now visible to every other connection. A run of forty rows becomes forty transactions, and
  a failure half-way rolls back only the last one — leaving precisely the half-written day that the
  ledger exists to prevent. Nothing raises, and no assertion about the *result* notices.

- **Why a test cannot merely assert the outcome.** A suite that checks "the run wrote its rows" or
  "a failure wrote no rows" can pass in both worlds: with per-row commits the failed run leaves the
  rows that committed *before* the failure, which looks identical to a run that failed before writing
  anything. The mechanism has to be asserted, not the intent.

- **Pattern.** Decide which layer owns the transaction, then make every write helper defer to it: the
  run opens the transaction and the helpers take a `commit: bool` (default `True`, so existing callers
  and tests are untouched) or are handed a transaction handle. Assert it three ways — the batch does not
  end the caller's transaction, a mid-batch failure rolls back **every** row of that batch, and a
  *negative control* that proves the test can see the problem: a bare `commit()` inside the explicit
  `BEGIN` does end it. Without that control the guard is a tautology.

- **Also worth knowing, from the same measurement:** `sqlite3.Connection.in_transaction` reflects
  SQLite's real autocommit state, so it stays `True` after an explicit `BEGIN` even with
  `isolation_level=None`. That property is what makes the assertion possible in the first place.

**Tags:** `#sqlite` `#transactions` `#atomicity` `#ingestion` `#gotcha`
