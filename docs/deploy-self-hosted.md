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

## 5. Security (Reverse Proxy)
If you want to access your dashboard from outside your home network, use a reverse proxy like **Traefik**, **Nginx Proxy Manager**, or **Cloudflare Tunnels**.

Example Traefik labels:
```yaml
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.garsync.rule=Host(`garsync.yourdomain.com`)"
      - "traefik.http.routers.garsync.entrypoints=websecure"
      - "traefik.http.routers.garsync.tls.certresolver=myresolver"
```

## 6. Performance on Raspberry Pi
- **SQLite WAL Mode:** Enabled by default in GarSync, this ensures the UI remains responsive even during a sync job.
- **Resources:** GarSync is very lightweight. It runs comfortably on a Raspberry Pi 3B+ or 4 with < 200MB RAM.
