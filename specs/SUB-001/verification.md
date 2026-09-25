---
tags: [spec, verification, migrations, alembic]
created: "2026-09-24"
---

# Verification - SUB-001

> Evidence produced in this session, on branch `feat/alembic-schema-migration`.

## Evidence

| Acceptance criterion | Evidence |
|---|---|
| **AC1** — one schema creator, on the caller's connection | `tests/test_migrations.py::TestAlembicSeam` (9 tests) — `test_init_db_leaves_the_schema_on_the_callers_connection` is the seam; `test_fresh_and_migrated_databases_are_identical` compares the structural shape of a fresh database against a stamped-and-migrated one; `test_the_baseline_reproduces_the_v1_schema` holds `0001_v1` against the frozen DDL; `test_upgrading_twice_changes_nothing`; `test_ddl_is_only_transactional_inside_an_explicit_transaction`; `test_init_db_leaves_the_connection_as_it_found_it`; `test_an_unrecognised_database_is_refused`; `test_v2_declares_no_foreign_keys` |
| **AC2** — no row lost, readers moved with writers | `TestRowPreservation` (5 tests) incl. `test_legacy_runs_are_copied_and_flagged` and `test_the_renamed_tables_keep_their_primary_key`; `tests/api/test_sync_status.py::test_counts_match_seeded_data` (value, not shape) and `::test_a_new_ingest_run_moves_the_count` (fails if the reader stayed on the old table); `tests/test_schema.py::TestInitDb::test_nothing_is_written_to_the_legacy_table` |
| **AC3** — UTC with a per-row offset and no assumed zone | `TestTimezoneNormalisation` (10 tests) — the three payload cases carry both offsets the real data contains (`-420`, `-480`) and a synthetic DST fold; `test_a_payload_without_an_offset_aborts_and_names_the_row`; `test_an_explicitly_configured_zone_resolves_the_straggler`; `tests/test_timeutil.py` (24 cases) covers the ingest path's own offset derivation |
| **AC4** — provenance and gaps explicit | `TestProvenanceAndGaps` (7 tests) — `test_source_and_source_id_are_unique_together`, `test_the_hrv_string_is_kept_verbatim_and_the_numbers_stay_null`, `test_derived_columns_come_from_the_payload`, `test_the_gap_count_is_queryable` |
| **AC5** — `goals` and nothing speculative | `TestGoalsAndNoSpeculativeTables` (3 tests) incl. `test_no_deferred_table_was_created` and `test_a_goal_without_a_start_date_is_refused` |
| **AC6** — contract frozen, gate green | `TestTheSnapshotBeforeTheMigration` (3 tests); `TestRealDatabaseRehearsal` (4 tests); `make check` → all targets ok (219 passed) |

### The rehearsal, on a copy of the only database

`TestRealDatabaseRehearsal` copies `data/garsync.db` to a temporary path, migrates the copy, and
checks the original's SHA-256 before and after. Measured on the copy:

| Fact | Before | After |
|---|---|---|
| `activities` rows | 100 | 100 |
| `biometrics` → `daily_metrics` | 4 | 4 |
| `sleep` → `sleep_sessions` | 4 | 4 |
| `sync_log` → `ingest_run` (`source='legacy'`) | 9 | 9 |
| `start_time` not ending in `Z` | 100 | **0** |
| rows without `tz_offset_minutes` | n/a (column did not exist) | **0** |
| distinct offsets | n/a | **{-420, -480}** |
| derived columns present | n/a | `aerobic_te` 100/100, `training_load` 2/100 |

The last row is the finding that changed the plan: `activityTrainingLoad` is absent from 98 of 100
list-endpoint payloads, so the metric layer inherits a measured gap (2%) rather than discovering it
after MET-001 is written.

## Test status

- Test suite: `make check` → lint ok · `mypy --strict` ok · **219 passed** · astro-check 0 errors · astro-build ok · docs-build ok
- Coverage: **84.07%** (904 statements, 144 missed). `.coverage-baseline` raised 83.03 → 84.07 in the
  same commit as the tests that raised it; the ratchet floor is now 82.07.
- No regressions: the four route-level suites (`/api/activities`, `/api/biometrics`, `/api/sleep`,
  `/api/sync/status`) pass with their assertions unchanged except where they asserted a value the
  change was meant to move (the two `records_synced`→`rows_upserted` renames and the sleep timestamp
  spelling).
- The real `data/garsync.db` was never opened for writing: every rehearsal runs on a `tmp_path` copy,
  and the digest assertion is what proves it.

## Decisions made during implementation

Each of these departs from `proposal.md` or from the task list as written, and each has a reason that
only became visible in the code.

1. **`batch_alter_table` for the renames, an explicit rebuild for `activities`.** R6 said "use batch,
   not a hand-rolled temp-table dance". That holds for `daily_metrics` and `sleep_sessions`, and it is
   what they use. It does **not** hold for `activities`: a batch *add* of a NOT NULL column requires a
   `server_default`, and the only honest default for `source` would have been `'garmin'` — a
   database-level default that silently labels a future scale row as Garmin, which is the one thing a
   provenance column exists to prevent. The explicit `op.create_table` + `INSERT … SELECT` + drop +
   rename has no residual default, derives every value in one statement, and is the artifact a
   reviewer can read.
2. **No `PRAGMA foreign_keys=OFF`.** The oracle's caveat ("issue it before the transaction, or it is a
   silent no-op") is right, and the pragma here would be ineffective *and* unnecessary: neither v1 nor
   v2 declares a foreign key, so a table recreate cannot orphan a reference.
   `test_v2_declares_no_foreign_keys` converts that assumption into a guard — if a foreign key ever
   arrives, the test fails and the rebuild mechanics have to be revisited deliberately.
3. **The transaction is taken away from the driver and issued by hand.** Measured, not assumed:
   `test_ddl_is_only_transactional_inside_an_explicit_transaction` shows a `CREATE TABLE` outside an
   explicit `BEGIN` survives a rollback, because pysqlite opens a transaction for DML and not for DDL.
   So the bridge sets `isolation_level = None` and emits `BEGIN` from a SQLAlchemy `begin` event, and
   restores the caller's isolation level afterwards. A first attempt — issuing `BEGIN` before handing
   the connection to SQLAlchemy — failed, because SQLAlchemy rolls back an open transaction when it
   checks the connection out.
4. **`source='legacy'` *and* `sync_type` retained.** §4.1 says the copied rows carry
   `source='legacy'`; the first draft of this spec replaced `sync_type` with `source`, which would
   have put a provenance value and a data class in one column and made `'legacy'` mean both "we did
   not record the source" and "the source was legacy". Two axes, two columns.
5. **`sleep_need` is called `sleep_need_seconds`.** The design names the column `sleep_need`; every
   neighbouring column carries its unit (`total_sleep_seconds`), and ADR-009 §3 makes units at rest a
   contract. The unit wins over the design's shorthand.
6. **`sync_log` is kept on fresh databases too.** The design says the legacy table stays read-only for
   one release, and the chain has no branch on "new" — one schema, produced one way. A fresh database
   therefore carries an empty `sync_log` until SUB-002 retires it. `test_the_v1_names_are_gone`
   asserts exactly that, and `test_nothing_is_written_to_the_legacy_table` asserts it stays empty.
7. **No `wal_checkpoint` before `VACUUM INTO`.** The task list called for one. `VACUUM INTO` already
   reads through the connection, so the write-ahead log is included; a checkpoint would only add a
   write to a database this code is otherwise reading.

### Environment findings, filed rather than absorbed

Two skews were found while adding the dependency, and neither is fixed here:

- **`poetry.lock` validates differently under different Poetry versions.** `poetry check --lock`
  **fails** on `master` with Poetry 2.2.1 (the local install) and **passes** with 2.5.1 (what CI
  installs, from `version: latest`). The lock was regenerated with 2.5.1 so CI and the branch agree.
- **The local virtualenv runs Python 3.13.11 while CI pins 3.12.** `requires-python = ">=3.12"` allows
  both, so "green locally" and "green in CI" were different claims. The venv was re-synced from the
  lock, which is what brought the two dependency sets back into agreement.

Both belong to the toolchain rather than the schema, so they are filed and **not** fixed here:
[#116](https://github.com/mlorentedev/garsync/issues/116) (CI-004). The lock was regenerated with
Poetry 2.5.1 — the version CI actually installs — so the branch and CI agree, and the venv was
re-synced from the lock, which is what brought the two dependency sets back into agreement.

### A consequence this PR introduces and declares rather than hides

Normalising to UTC changed which calendar day a row belongs to. Three endpoints bucket or filter with
`date(start_time)`: `/api/stats/heatmap`, `/api/activities` (date filters) and `/api/stats/summary`.
After the migration the same expression returns the **UTC** day, and **2 of the 100** real activities
land on a different day than the one they were recorded on — a session recorded at `2026-01-10
21:48:59` local is stored `2026-01-11T04:48:59Z` and now counts as the 11th.

It is not fixed here on purpose: *which* day an activity belongs to is a product decision (the day it
was recorded locally, or `GARSYNC_TZ`'s calendar day per ADR-008 §11), and it has to be settled once,
where `derived_daily` is built, so the heatmap, the metric series and the weekly review cannot
disagree. Filed as [#115](https://github.com/mlorentedev/garsync/issues/115) (SUB-005) with the
measured evidence and the alternatives.

## Promotion candidates

- [ ] Lesson for the repo's `docs/lessons/`? **yes — three:**
  1. **A payload-carried offset beats a configured zone.** The first draft proposed `Europe/Madrid` as
     the fallback for `GARSYNC_TZ`; the real activities are Garmin `timeZoneId` 153/121 (US
     Mountain/Pacific, `-420`/`-480`), so that default would have been ~8 hours wrong on the very
     history it was applied to — and no fixture could have caught it, because the fixture would have
     encoded the same assumption.
  2. **Moving a writer without its reader freezes an endpoint silently.** Declaring `sync_log`
     read-only implies moving its writer, but its single reader reads the same table; a route test
     asserting a *shape* stays green while the number freezes. The test has to assert a value and its
     increment.
  3. **SQLite commits DDL outside an explicit transaction, and SQLAlchemy rolls back a transaction it
     did not open.** Both were measured here; together they are why a migration can look atomic and
     leave a database that is neither version.
- [ ] ADR-worthy decision for the repo's `docs/adr/adr-XXX.md`? **candidate: an ADR-009 amendment**
  recording that revisions are hand-written Core ops, that `autogenerate` is forgone permanently, and
  that the drift assertion in AC1 is the substitute. ADR-009 lists autogenerated diffs as a benefit of
  the choice, so the cost belongs in the record it belongs to. Decide at archive.
- [ ] New pattern candidate for `00_meta/patterns/`? **no** — all three lessons above are repo-local.

## Archive checklist

- [ ] `proposal.md` frontmatter set to `status: archived`
- [ ] `specs/SUB-001/` → `specs/archive/SUB-001/`, after a passing adversarial review
      (`dotf spec review SUB-001`) — the implementer cannot sign it
- [ ] Bitácora: issue #82 closed with the PR link (ADR-018 → Done)
- [ ] Promotions above executed
