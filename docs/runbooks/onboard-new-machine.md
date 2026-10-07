# Runbook: bring garsync up on a new machine

A `git clone` reproduces the code, the ADRs, the lessons and the specs. It does **not** reproduce
three things that live only on the old disk. Carry those by hand first, then follow the steps.

## What travels, and how

| What | Where it lives | How it reaches the new machine |
|---|---|---|
| Code, `docs/`, `specs/`, `harness/` | this repository | `git clone` |
| Issues, the bitácora board, Actions secrets (`BITACORA_PAT`, `NAN_API_KEY`), Pages, Dependabot, Release Please | GitHub (`mlorentedev/garsync`) | nothing to do while the owner stays the same |
| Session memory (`MEMORY.md`, session journals) | the knowledge vault, `10_projects/garsync/memory/` | clone the vault; the dotfiles setup links `~/.claude/projects/<path-hash>/memory` to it |
| **The age identity** `~/.config/age/garsync.txt` | old disk only | **copy by hand** |
| **The database** `data/garsync.db` | old disk only (`data/` is gitignored) | **copy by hand** |
| Personal Claude skills in `.claude/skills/` | old disk only (`.claude/` is gitignored) | optional; copy by hand if still wanted |

Not worth carrying: `frontend/.env` (it holds `PUBLIC_API_URL=http://localhost:8000`, which is the
default in `frontend/src/lib/api.ts`), `data/sync_result.json` (a root-owned output of an old
container run), `.coverage`, `specs/**/review-transcript.jsonl*` (launcher logs; the signed
`review.md` is tracked).

## 1. The age identity

garsync's `secrets.env.enc` is encrypted to **one dedicated recipient**,
`age132cnnnxv7evunrw7qa7n0f8e8pjxu5rdqwnpdjqmtkx3ka4yx33qngfd76` (see `.sops.yaml`). The
machine-wide key (`~/.config/age/key.txt`, `~/.config/sops/age/keys.txt`) **does not decrypt it**;
this is **deliberate, not an oversight**: SEC-001's secrets hardening
(`specs/archive/SEC-001/proposal.md`, lesson 004) moved garsync to its own identity, outside the
master/password-manager key chain, and removed the master recipient with `sops updatekeys`. Do not
"fix" it by adding the master key back to `.sops.yaml`; carry `garsync.txt` instead, to the same
path on macOS and Linux.

```sh
mkdir -p ~/.config/age
install -m 600 /path/to/carried/garsync.txt ~/.config/age/garsync.txt   # BSD install has no -D
age-keygen -y ~/.config/age/garsync.txt   # must print the recipient above
```

The Makefile reads it through `GARSYNC_AGE_KEY` (default `~/.config/age/garsync.txt`) and sets
`SOPS_AGE_KEY_FILE` from it unconditionally, so a shell that exports the machine-wide key does not
take precedence. Verify by consequence. Never print the output:

```sh
SOPS_AGE_KEY_FILE=~/.config/age/garsync.txt \
  sops -d --input-type dotenv --output-type dotenv secrets.env.enc >/dev/null; echo $?   # 0
```

To edit the secrets (the Makefile's export applies only inside its own recipes, so an
interactive shell needs the key named explicitly):

```sh
SOPS_AGE_KEY_FILE=~/.config/age/garsync.txt \
  sops --input-type dotenv --output-type dotenv secrets.env.enc
```

`--input-type dotenv` is required: without it sops treats the unknown `.enc` extension as its binary store (lesson 037) and fails
with `invalid character … looking for beginning of value`, which looks like a key problem and is
not one.

If this key is lost, the Garmin credentials can be re-entered and re-encrypted to a new identity.
Nothing else depends on it.

## 2. Toolchain and the gate

Match what CI runs: **Python 3.12** and **Node 22** (`.github/workflows/`). Poetry is not pinned
(#116); on the old machine the local `.venv` had drifted to Python 3.13.11 while CI runs 3.12 (Poetry 2.2.1, Node 24 locally). On a fresh machine, pin it before `make setup`: `poetry env use python3.12`.

```sh
git clone https://github.com/mlorentedev/garsync.git ~/Projects/garsync
cd ~/Projects/garsync
make setup
make check        # must end with "✓ All checks passed"
```

Clone to `~/Projects/garsync`. Claude Code names its per-project memory directory after the
*absolute* path, so on macOS it becomes `-Users-<user>-Projects-garsync` rather than
`-home-<user>-…`; the dotfiles setup derives the vault link from the absolute path (`setup-linux.sh`;
macOS setup is tracked in dotfiles#2013), so run it after the clone and check that `~/.claude/projects/*garsync/memory` resolves into the vault.

## 3. The database

As of 2026-10-06 the real database is still **schema v1** (`schema_version = 1`, no
`alembic_version` table): 100 activities, 4 biometrics days, 4 sleep days, 9 `sync_log` rows, last
biometrics day 2026-03-01. The v1→v2 migration has been run on a copy only (SUB-001).

Run this from the repository root, after `make setup` and before anything opens the database
(`make check` uses temporary databases and does not):

```sh
cd ~/Projects/garsync
mkdir -p data && cp /path/to/carried/garsync.db data/garsync.db
make db-backup     # snapshot before anything opens it
```

The first process that opens it with current `master` runs the Alembic chain and migrates it to
v2, after taking its own snapshot (`src/garsync/db/schema.py`). Keep the carried copy until the
migrated database has been checked.

**Do not count on re-syncing from Garmin to rebuild it.** As of late September 2026 Garmin's edge
returned 429 (mobile) and a Cloudflare 403 (portal) with no token cache, and retrying a
rate-limited login prolongs the block (lesson 030, which lands with PR #131). Running `make sync` repeatedly to "test" the
new machine makes this worse.

## 4. Where the work stood at migration (2026-10-06)

- `master` = `ee0f28e`, CI green; `make check` green on SUB-002's tip as well (332 tests, 87.43 %).
- **SUB-002 (#83)** is a **draft PR, #131**: blocks 1–6 of 7 done. Block 7 (the `0003` chain tests and
  widening `f12`) and an independent adversarial review are owed before it leaves draft.
- Open and waiting for the owner: release-please **#125** (0.3.1) and the Dependabot PRs.
- The board (bitácora) is the source of truth for what comes next. The vault's
  `10_projects/garsync/memory/MEMORY.md` holds the session handoff.
