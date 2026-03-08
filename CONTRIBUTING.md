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

1. Create a feature branch from `main`.
2. Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`).
3. Run `make check` before pushing.
4. Open a PR — CI will run automatically.

## Code Standards

- **Python:** PEP8, Type hints (mypy --strict), Ruff for linting.
- **Frontend:** Astro (TypeScript) with Islands Architecture.
- **Complexity:** Functions < 40 lines, nesting < 4 levels.
- **Tests:** Mandatory for all new features and bug fixes.

## Release Process

Automated via [release-please](https://github.com/googleapis/release-please).
Conventional commits on `main` trigger version bumps and changelog updates.
