# Self-Hosted Deployment Guide

This guide describes how to deploy GarSync on your own hardware (Raspberry Pi, Synology NAS, or any Linux server) for automated data ownership.

## 1. Prerequisites
- Docker & Docker Compose installed.
- (Optional but recommended) [SOPS](https://github.com/getsops/sops) for secrets.

## 2. Deployment Structure
Recommended folder structure on your server:
```
garsync/
├── docker-compose.yml
├── secrets.env.enc  (or .env)
├── key.txt          (if using SOPS)
└── data/            (sqlite database will live here)
```

## 3. Docker Compose Configuration
Use the following `docker-compose.yml`:

```yaml
services:
  garsync:
    image: garsync:latest # Or build from source
    container_name: garsync
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - GARSYNC_DB_PATH=/app/data/garsync.db
      - TZ=Europe/Madrid # Set your timezone
```

## 4. Automated Sync (Cron)
To keep your dashboard up-to-date, you should schedule the sync pipeline. The most reliable way is to run a temporary container that shares the same database volume.

Add this to your crontab (`crontab -e`):

```bash
# Sync every day at 4:00 AM
0 4 * * * cd /path/to/garsync && /usr/local/bin/docker compose run --rm --entrypoint "garsync --days 7 --db /app/data/garsync.db" garsync
```

*Note: This assumes your Garmin credentials are baked into the image or provided via environment variables in the sync command.*

## 5. Authentication (required before exposing the dashboard)

Since v0.2.0 the API and the dashboard are protected by an application-level gate. Configure it through environment variables in `docker-compose.yml` (or your secrets file):

| Variable | Purpose |
|---|---|
| `GARSYNC_ACCESS_PASSWORD` | Password for the `/login` page. A correct login sets a signed, `HttpOnly; SameSite=Lax; Secure` session cookie valid for 7 days. Rotating the password invalidates all sessions. **Set this before publishing the dashboard.** |
| `GARSYNC_API_KEY` | Key for programmatic access to `/api/*` via the `X-API-KEY` header (e.g. scripts, cron). Missing header returns 401, wrong key returns 403. |
| `GARSYNC_ALLOWED_ORIGINS` | Optional comma-separated list of explicit origins for CORS. Leave unset for a same-origin deployment (the default). `*` is rejected at startup because requests carry credentials. |
| `GARSYNC_INSECURE_COOKIES` | Set to `1` only for local development over plain `http://`; it drops the `Secure` flag so the browser sends the session cookie. Never set it behind HTTPS. |

If **neither** `GARSYNC_ACCESS_PASSWORD` nor `GARSYNC_API_KEY` is set, the application starts unprotected and logs a warning. That mode is only acceptable on a trusted local network.

If only `GARSYNC_API_KEY` is set, `/api/*` requires the key but the dashboard pages are still served without a password (the application logs a warning at startup). Do not expose the dashboard in that configuration; whether it should be rejected outright is tracked in [#51](https://github.com/mlorentedev/garsync/issues/51).

Failed logins are rate-limited per client IP (5 failures per 5 minutes, then 429). The limiter is in-memory and resets when the container restarts. The client IP is taken from the direct connection (`request.client.host`), so behind a reverse proxy every visitor shares the proxy's address and the same bucket; proxy-aware IP handling and a login origin check are tracked in [#50](https://github.com/mlorentedev/garsync/issues/50) and must land before the dashboard is exposed publicly.

## 6. Security (Reverse Proxy)
If you want to access your dashboard from outside your home network, use a reverse proxy like **Traefik**, **Nginx Proxy Manager**, or **Cloudflare Tunnels**.

Example Traefik labels:
```yaml
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.garsync.rule=Host(`garsync.yourdomain.com`)"
      - "traefik.http.routers.garsync.entrypoints=websecure"
      - "traefik.http.routers.garsync.tls.certresolver=myresolver"
```

## 7. Performance on Raspberry Pi
- **SQLite WAL Mode:** Enabled by default in GarSync, this ensures the UI remains responsive even during a sync job.
- **Resources:** GarSync is very lightweight. It runs comfortably on a Raspberry Pi 3B+ or 4 with < 200MB RAM.
