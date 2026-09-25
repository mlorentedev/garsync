---
id: lesson-026-moving-a-writer-without-its-reader-freezes-an-endpoint
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, sqlite, refactor, api, testing, gotcha]
---

# Moving a writer without its reader freezes an endpoint silently

- **Context:** `specs/SUB-001`. The design declares `sync_log` read-only for one release and replaces
  it with `ingest_run`. The spec as first written scoped the change as *"the writer moves"* —
  `pipeline.py` logs through `SyncLogRepository`, and the v1 table stops receiving writes.
- **Finding:** independent review of the plan found the other half. `SyncLogRepository.count()` reads
  the same table, and its single consumer is `GET /api/sync/status` (`total_sync_logs`). Had only the
  writer moved, the endpoint would have kept reporting the **old table's** rows forever — a number
  frozen at 9 — and the route's own test would have stayed green, because it asserted a **shape**
  (`"total_sync_logs" in data`) and a stale count satisfies a shape. A refactor that removes writes
  from a table does not make its readers harmless; it makes them *quiet*.
- **Pattern:** a table that stops being written is a table whose **every reader is now a bug**, so
  move them in the same commit as the writer, and assert a **value that moves** rather than a field
  that exists. The regression test here appends a run through the repository and asserts the endpoint
  count **increments** — which fails if either half of the move is left behind. More generally: when a
  behaviour is maintained by two pieces of code, "the diff is smaller if I only touch one" is the
  shape of the bug, and the missing half is normally the one with no error, no log line, and no
  failing test.
- **Related judgement, same change:** the new table separates two axes that were conflated in the old
  one — `source` (*where the data came from*) and `sync_type` (*which class of data the run covered*).
  Collapsing them into a single `source` column would have made `'legacy'` mean both "no source was
  recorded" and "the source was legacy", which is a provenance lie that no constraint can catch.

**Tags:** `#sqlite` `#refactor` `#api` `#testing` `#gotcha`
