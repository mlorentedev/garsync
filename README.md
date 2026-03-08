# GarSync

[![CI](https://github.com/mlorentedev/garsync/actions/workflows/ci.yml/badge.svg)](https://github.com/mlorentedev/garsync/actions)
[![Docs](https://img.shields.io/badge/docs-live-brightgreen.svg)](https://mlorentedev.github.io/garsync/)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Personal fitness data pipeline that syncs Garmin Connect data to a local SQLite database and visualizes it through a modern Astro dashboard.

> **Explore the full documentation at: [mlorentedev.github.io/garsync](https://mlorentedev.github.io/garsync/)**

## The Problem

Garmin Connect provides great data, but it's locked in a proprietary cloud.
- **Data Silos:** Hard to export full history for custom analysis.
- **Limited Visualization:** You are stuck with the official app's charts.
- **No Local Ownership:** If you lose access or the service is down, your training history is gone.

## Value Proposition

| Feature | Garmin Connect App | GarSync |
|---|---|---|
| **Data Ownership** | Proprietary Cloud | Local SQLite (Full Control) |
| **Customization** | Fixed Dashboards | Extensible Astro + Chart.js |
| **Access** | Web/Mobile Only | REST API + SQL + CLI |
| **Automation** | Manual Export | Scheduled Incremental Sync |

## Quick Start

### 1. Prerequisites
- Python 3.12+ and [Poetry](https://python-poetry.org/)
- Node.js 22+ (for the dashboard)
- [SOPS](https://github.com/getsops/sops) + [Age](https://github.com/FiloSottile/age) (for secrets)

### 2. Setup
```bash
make setup
```

### 3. Configure Secrets
Edit your Garmin credentials using SOPS:
```bash
sops secrets.env.enc
```

### 4. Sync & Launch
```bash
make sync DAYS=30
make dev
```
Visit `http://localhost:4321` (Dev UI).

## Architecture

```
Garmin Connect Cloud → GarSync CLI → SQLite DB → FastAPI → Astro Dashboard
```

## License

MIT — see [LICENSE](LICENSE).
