# AGENTS.md

> **Canonical instructions for every AI coding agent in this repository** (Claude Code, Copilot,
> Cursor, Codex, Gemini/Antigravity, pi, …). `CLAUDE.md` is a thin pointer for Claude-specific
> notes; per-agent files never carry rules that belong here — if one contradicts this file, this
> file wins.

GarSync is a **private, single-user** training and body-composition pipeline: Garmin Connect and a
FitDays smart scale in, one auditable metric layer, an Astro dashboard and a weekly review out.
Every number must be traceable to a formula and a source row.

**v2 is in progress.** The design of record is
[`docs/architecture/target-architecture-v2.md`](docs/architecture/target-architecture-v2.md), and
the decision register is
[`docs/architecture/scope-interview.md`](docs/architecture/scope-interview.md) (SC-01…SC-19).
**The register is the authority: where the design contradicts it, the register wins.**

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, Typer CLI (`garsync`).
- **Database:** SQLite in WAL mode (dev + tests today; PostgreSQL is the production target per
  [ADR-009](docs/adr/adr-009-data-substrate-and-migrations.md)).
- **Frontend:** Astro (islands) + Tailwind CSS + Chart.js + Nano Stores, in `frontend/`.
- **Tooling:** Poetry, Ruff, `mypy --strict`, pytest, Docker Compose, SOPS + age for secrets.
- **Docs site:** Astro Starlight in `docs-site/` (published to GitHub Pages).

## Key Paths

| Path | Purpose |
|---|---|
| `src/garsync/cli.py` | Typer entry point — orchestration only; sync logic lives in `pipeline.py` |
| `src/garsync/pipeline.py` | `SyncService` — Garmin fetch → normalise → upsert |
| `src/garsync/client.py` | Garmin client (token caching, login fallback, retries) |
| `src/garsync/db/` | `schema.py` (runs the Alembic chain on the caller's connection), `migrations/` (the DDL, as revisions), `backup.py` (pre-migration snapshot), `connection.py`, `repository.py` (the only SQL layer) |
| `src/garsync/api/` | FastAPI app factory, `auth.py` (session gate, rate limiter), `routes/` |
| `frontend/src/components/` | Dashboard islands (`Heatmap`, `TrendChart`, `KpiCards`, …) |
| `frontend/src/lib/api.ts` | Fetch wrappers; **no credentials in the client** |
| `tests/` | pytest suite; `tests/api/` covers routes and auth, `test_integration_full.py` is the end-to-end path |
| `docs/adr/` | Architecture Decision Records — the *why* |
| `docs/architecture/` | Design of record, scope register, research briefs, ticket plan |
| `docs/lessons/` | One lesson per file + `_index.md`; `docs/lessons.md` is a pointer stub |
| `scripts/` | Toolchain-free guards run by CI: `check-lessons.sh`, `check-actions-pinned.sh` |
| `harness/` | Review gates read by `dotf`: `review-attestation.json`, `reviewer-pool.json` |
| `specs/` (`specs/archive/`) | Per-feature SDD folders (proposal + tasks + verification) |

## Commands

```sh
make setup            # Bootstrap Poetry venv + frontend node_modules
make check            # The gate: lint + type + test + frontend check/build (CI runs the same)
make dev              # API on :8000 + Astro dev server on :4321
make sync DAYS=7      # Garmin ingest (needs the SOPS age key)
make db-backup        # Snapshot the database before a migration rewrites it
make smoke            # E2E smoke: API endpoints + frontend build (needs data/garsync.db)
make format           # ruff --fix + ruff format
```

Never invent a second way to run a check: `make check` is the one surface, and CI calls the same
targets so the two cannot drift.

## Architecture Decisions

Full index: [`docs/adr/`](docs/adr/) (docs-as-code; the directory is the index). Current state:

- **ADR-004** API-key auth for `/api/*` — amended by ADR-006; [ADR-010](docs/adr/adr-010-access-and-sharing-model.md) replaces `X-API-KEY` with one scoped, hashed, read-only agent token.
- **ADR-005** cloud-LLM coach (`POST /api/ai/chat`) — **superseded**; there is no language model in
  v2 (SC-11, [ADR-013](docs/adr/adr-013-analytics-and-recommendation-discipline.md)).
- **ADR-006** single-user session gate — amended by ADR-010 (server-side revocable sessions).
- **ADR-007…013** accepted: purpose-built single-user platform · ingestion ledger and adapters ·
  storage substrate and migrations · access and sharing · deployment topology · scale integration
  route · analytics and recommendation discipline.

**The schema is owned by Alembic.** `src/garsync/db/migrations/` holds the only DDL: `schema.py`
runs the chain on the connection it is handed and takes a snapshot first when a migration is pending.
A migration is never a `sqlalchemy.url` away — the chain has no URL, because a connection Alembic
opens itself is a different database from the caller's (and for the `:memory:` fixtures, an empty
one).

## Documentation & Knowledge Placement

Build/operate knowledge lives **in this repo**, versioned with the code:

- architectural decision → `docs/adr/adr-NNN-<slug>.md`
- design/proposal → `docs/architecture/`
- project lesson or gotcha → `docs/lessons/lesson-NNN-<slug>.md` **plus its row in
  `docs/lessons/_index.md`** (the pairing is guarded by `scripts/check-lessons.sh`; appending to
  `docs/lessons.md` recreates the monolith the pointer stub replaced)
- troubleshooting/deployment → `docs/`

Cross-project insight goes to the maintainer's knowledge store (patterns, methodology); task state
lives on the bitácora GitHub Project, never in a doc.

## Workflow Rules (read before the first tool call)

- **Issue first.** Every change starts from an open bitácora issue; self-assign it at pickup
  (that flips the board to *In Progress*). No issue, no branch.
- **Spec-Driven Development** when any of these is true: ~50–300 executable lines of production
  diff (tests, generated files and lockfiles excluded), a public contract (API, CLI flag, exported
  type, deployed config schema) is touched, a dependency is added, it is the first step of a
  multi-PR sequence, or it warrants a Socratic pause (architecture, schema, concurrency, breaking
  change). Then: `dotf spec init <feature-id> --issue <N>` → `proposal.md` before code →
  `tasks.md` in TDD order → implement → `verification.md` with evidence → archive on merge.
  Skip for typos, comment-only edits, mechanical refactors, <20-line bug fixes with an obvious
  cause, and doc-only or config-only changes.
- **TDD.** Failing test first, then the fix. Table-driven tests for parsers and repositories;
  fixtures for anything a hand-computed value can be checked against.
- **Atomic PRs**, ~300 executable lines max. An overage is allowed only if declared in the PR body
  with the seam that was rejected.
- **No auto-merge, ever.** A PR merges only after the owner has reviewed it and CI is green; an
  agent merges only when the owner has authorized *that* PR.
- **PR stewardship.** Run `dotf pr triage-queue` at session start and again before claiming any PR
  work complete, and give every reviewer comment a disposition in a `## Review triage` comment on
  the PR — including "CI green, no findings", which is a disposition too.
- **English only** in commits, branch names, PR/issue titles and bodies, and code comments. **No AI
  attribution**: no `Co-Authored-By` referencing an agent, no "generated with" footers, no bot
  emojis. Conversation with the owner may be in any language; the durable record is English.
- **Secrets.** `secrets.env.enc` is SOPS-encrypted, and `data/` is gitignored. Never print a secret
  to stdout, never `cat` a decrypted store, never commit plaintext credentials. Inject them into the
  process that consumes them (`dotf secrets run -- <cmd>`, or the `make sync` path). Do not edit
  `.sops.yaml` or the encrypted files unless the owner asks for it.
- **Scripts under `scripts/`** must run under both bash and zsh, and are ShellCheck-clean.

### Review gates are repo-owned config (`harness/`)

Two mechanisms read `harness/` and answer *nothing* where it is absent, so they are wired here
rather than assumed:

- **`dotf pr triage-queue`** — exit 0 means no reviewer output awaits a disposition. Exit 1 means
  either that work is pending **or that the question could not be answered**; read the message, not
  just the code.
- **`dotf spec archive`** — refuses a `review.md` signed by a model outside
  `harness/reviewer-pool.json`, so an adversarial review never runs on an Anthropic model here, and
  the implementer is never the reviewer. Known limitation: the pool's provider-diverse arm
  (`agy/gemini-3.1-pro-high`) is **not launchable from pi**, recorded in
  [`docs/architecture/review-v2-pass1.md`](docs/architecture/review-v2-pass1.md).

## Conventions

- Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`).
- GitHub Flow: branch from `master`, PR back into `master`, squash merge.
- PR body ends with `Closes #N` per issue resolved, so the bitácora closes with the change.
- Functions < 40 lines, nesting < 4 levels, cyclomatic complexity < 10.
- Stdlib before a new dependency; a new runtime dependency needs a stated reason.
