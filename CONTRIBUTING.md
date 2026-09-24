# Contributing

## Setup

```bash
git clone https://github.com/mlorentedev/garsync.git
cd garsync
make setup
```

## Development

| Command | Purpose |
|---|---|
| `make check` | Run all quality checks (lint, type, test) |
| `make test` | Run tests only |
| `make dev` | Start API and Frontend in dev mode |
| `make sync` | Sync data from Garmin (requires SOPS key) |

## Pull Requests

1. Open (or reuse) an issue on the [bitácora board](https://github.com/users/mlorentedev/projects/1)
   and self-assign it — the board moves it to *In Progress*. No issue, no branch.
2. Create a feature branch from `master`.
3. Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`).
4. Run `make check` before pushing — CI runs the same targets.
5. Open a PR — CI will run automatically. Add `Closes #N` per issue resolved.

The full workflow rules (Spec-Driven Development, atomic PRs, review gates, secrets) live in
[`AGENTS.md`](AGENTS.md) — read that once before contributing.

## Code Standards

- **Python:** PEP8, Type hints (mypy --strict), Ruff for linting.
- **Frontend:** Astro (TypeScript) with Islands Architecture.
- **Complexity:** Functions < 40 lines, nesting < 4 levels.
- **Tests:** Mandatory for all new features and bug fixes.

## Release Process

Automated via [release-please](https://github.com/googleapis/release-please).
Conventional commits on `master` trigger version bumps and changelog updates.
