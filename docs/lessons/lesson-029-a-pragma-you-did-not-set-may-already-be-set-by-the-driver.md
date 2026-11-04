---
id: lesson-029-a-pragma-you-did-not-set-may-already-be-set-by-the-driver
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, sqlite, verification, defaults, measurement, gotcha]
---

# A pragma you did not set may already be set by the driver

Measured in `specs/SUB-002`, while checking a claim that turned out to be false.

- **Finding.** `src/garsync/db/connection.py` sets `journal_mode=WAL` and `foreign_keys=ON` and nothing
  else, so it is natural to record "no `busy_timeout`" — and that is what a written brief asserted. The
  effective setting is **5000**:

  ```
  sqlite3.connect(p).execute("PRAGMA busy_timeout").fetchone()[0]
  → 5000
  sqlite3.connect(p, isolation_level=None).execute("PRAGMA busy_timeout").fetchone()[0]
  → 5000
  ```

  The value comes from `sqlite3.connect`'s own `timeout=5.0` parameter, which pysqlite turns into that
  pragma. SQLite's documented default for the pragma is `0`, so both available sources — this repo's
  connection helper and the database's own documentation — give a *wrong* answer to the question
  "what is the busy timeout?". Only the running connection has the right one.

- **Why it mattered here.** The claim was load-bearing: it was the stated reason for a decision
  ("add an explicit `busy_timeout`"). The decision survived, but for a different reason — making a chosen
  five seconds explicit and justified beats leaving a driver default nobody looked up — and the
  difference between *absent* and *implicit* is exactly what a future reader would get wrong.

- **Pattern.** An absence claim has to be measured **where the value is consumed**, not where it is
  configured, and not in the documentation of the layer you were reading. When the answer comes from a
  library default rather than a line in the repository, say so in the docstring that owns the setting —
  `timeout=5.0 → PRAGMA busy_timeout=5000` is one line and it stops this from being re-derived.

**Tags:** `#sqlite` `#verification` `#defaults` `#measurement` `#gotcha`
