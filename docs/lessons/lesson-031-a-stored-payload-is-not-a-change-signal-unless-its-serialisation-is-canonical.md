---
id: lesson-031-a-stored-payload-is-not-a-change-signal-unless-its-serialisation-is-canonical
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, idempotency, json, sqlite, testing, gotcha]
---

# A stored payload is not a change signal unless its serialisation is canonical

Measured in `specs/SUB-002`, while proving an idempotency contract (`ADR-008` §5: a re-pull changes zero
rows **and** zero values).

- **Finding 1 — the two re-pulls in the first probe were not two serialisations.** The probe compared a
  stored payload against `repo.upsert(row)` where `row["raw_data"]` was *the string read back from the
  table*. Byte-identical by construction, so the experiment could only ever measure the UPSERT, never the
  serialiser. A re-pull that reuses the stored text tests nothing about re-serialisation.

- **Finding 2 — the stored text is not canonical.** Parsing a stored payload and dumping it again gives
  a *different* string of the *same* length:

  ```
  d = json.loads(stored); json.dumps(d) == json.dumps(dict(sorted(d.items())))
  → False       # bytes: 3303 vs 3303
  ```

  Same bytes, different order: the upstream key order is not alphabetical. So a change predicate written
  as `excluded.raw_data IS NOT activities.raw_data` fires on key order alone — inflating
  `rows_upserted`, churning `updated_at` on every run, and turning "zero changed values" into a claim
  that is false for reasons nobody can see in the diff.

- **Pattern.** Whichever way it is resolved, resolve it **once and on purpose**: either the write path
  canonicalises (sort keys, fixed separators) so two pulls of the same payload produce the same text, or
  the predicate compares a canonical form rather than the text. Then declare the landing cost — the first
  pass over already-stored rows rewrites them and legitimately reports changes — and assert the
  idempotency contract on the **second** pass, feeding the second pull a freshly serialised payload.
  A stored-blob comparison is only as strong as the determinism of the thing that wrote the blob.

**Tags:** `#idempotency` `#json` `#sqlite` `#testing` `#gotcha`
