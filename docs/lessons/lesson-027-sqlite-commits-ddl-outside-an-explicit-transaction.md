---
id: lesson-027-sqlite-commits-ddl-outside-an-explicit-transaction
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, sqlite, sqlalchemy, alembic, transactions, gotcha]
---

# SQLite commits DDL outside an explicit transaction, and SQLAlchemy rolls back what it did not open

Two facts, measured on this stack in `specs/SUB-001`, that together decide whether a migration is
atomic or merely looks it.

- **Finding 1 — the driver's implicit transaction covers DML only.** Python's `sqlite3` opens a
  transaction before an `INSERT`/`UPDATE`/`DELETE` when `isolation_level` is left at its default, and
  **never before DDL**. So `CREATE TABLE` outside an explicit `BEGIN` commits the moment it runs:

  ```
  conn.execute("CREATE TABLE outside (x INTEGER)"); conn.rollback()
  → "outside" is still there            # a rollback that rolled back nothing
  conn.execute("BEGIN"); conn.execute("CREATE TABLE inside (x INTEGER)"); conn.rollback()
  → "inside" is gone                    # SQLite *is* transactional for DDL, given a transaction
  ```

  SQLite is not the problem; the driver's default mode is. A migration that relies on
  `with context.begin_transaction()` without arranging for a real `BEGIN` is a series of independent
  commits, and a failure half-way leaves a database that is neither the old version nor the new one.

- **Finding 2 — SQLAlchemy rolls back a transaction it did not open.** The first fix attempted was the
  obvious one: issue `BEGIN` on the connection, then hand that connection to SQLAlchemy (the app owns
  it, and for `:memory:` a second connection is a second empty database, so it has to be *this* one).
  It fails. Checking a connection out resets it, and the manual `BEGIN` — and the DDL already
  committed under it — is gone:

  ```
  conn.execute("BEGIN"); conn.execute("CREATE TABLE t (x INTEGER)")
  engine = create_engine("sqlite://", creator=lambda: conn, poolclass=StaticPool)
  engine.connect().execute(text("INSERT INTO t VALUES (1)"))
  → OperationalError: no such table: t
  ```

- **Pattern:** take the `BEGIN` away from the driver and give it to the layer that manages the
  transaction. Set `isolation_level = None` (so pysqlite stops deciding when to start one) and emit
  `BEGIN` from a SQLAlchemy `begin` event, then restore `isolation_level` afterwards because the
  connection belongs to the caller and is about to be used by the application. `VACUUM INTO` cannot run
  inside a transaction, and `PRAGMA foreign_keys` is a **silent no-op** inside one — both are symptoms
  of the same rule: know which layer owns the transaction before adding a statement that needs to be
  outside it.
- **Testing gotcha, worth its own line:** the invariant is easy to *state* and easy to lose, so assert
  the mechanism, not the intent — a test that a table created inside an explicit `BEGIN` disappears on
  rollback, and another that the caller's connection comes back usable and unchanged. A migration test
  that only checks "the migration applied" passes in both worlds.

**Tags:** `#sqlite` `#sqlalchemy` `#alembic` `#transactions` `#gotcha`
