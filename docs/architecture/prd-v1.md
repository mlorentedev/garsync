---
id: "garsync-prd-v1"
type: project
status: active
tags: [garsync, prd, v1, mvp]
created: "2026-02-28"
owner: manu
---

# GarSync V1 — Product Requirements Document

> **Goal:** Pipeline robusto con persistencia SQLite, sync incremental, y dashboard Astro interactivo con calendar heatmap y métricas de tendencias.

## 1. Problem Statement

Garmin Connect ofrece datos de entrenamiento pero con limitaciones:
- No permite queries analíticas sobre datos históricos
- Dashboard no personalizable
- Sin correlaciones entre métricas (sueño vs rendimiento)
- Sin tipos de entrenamiento personalizados
- Los datos están atrapados en su plataforma

GarSync V1 resuelve la **extracción y visualización** — la base para features de IA posteriores.

## 2. User Persona

**Manu** — Ingeniero de software que entrena regularmente (cardio variado, HIIT, intervalos, periodización). Quiere ver sus datos de forma más útil que lo que ofrece Garmin. También es un proyecto de portfolio que demuestra skills full-stack.

## 3. Functional Requirements

### FR-1: Persistencia SQLite

| Req | Descripción | Prioridad |
|-----|-------------|-----------|
| FR-1.1 | Schema con tables: `activities`, `biometrics`, `sleep`, `sync_log` | Must |
| FR-1.2 | Migraciones versionadas del schema | Must |
| FR-1.3 | Índices en `date` y `activity_id` para queries rápidas | Must |
| FR-1.4 | DB file en `data/garsync.db` (volumen Docker) | Must |

### FR-2: Sync Incremental

| Req | Descripción | Prioridad |
|-----|-------------|-----------|
| FR-2.1 | Detectar último sync timestamp y solo descargar datos nuevos | Must |
| FR-2.2 | Upsert: actualizar si el registro ya existe (por `activity_id` o `date`) | Must |
| FR-2.3 | Log de cada sync en `sync_log` (timestamp, records_added, errors) | Must |
| FR-2.4 | CLI mantiene opciones actuales (`--days`, `--activities-limit`) | Must |
| FR-2.5 | Output JSON sigue funcionando (backward compatible) | Should |

### FR-3: FastAPI Backend

| Req | Descripción | Prioridad |
|-----|-------------|-----------|
| FR-3.1 | `GET /api/activities` — Lista paginada con filtros (fecha, tipo) | Must |
| FR-3.2 | `GET /api/biometrics` — Biometrics por rango de fechas | Must |
| FR-3.3 | `GET /api/sleep` — Sleep data por rango de fechas | Must |
| FR-3.4 | `GET /api/stats/summary` — KPIs agregados (último mes/semana) | Must |
| FR-3.5 | `GET /api/stats/heatmap` — Datos para calendar heatmap (365 días) | Must |
| FR-3.6 | `GET /api/sync/status` — Último sync, total records | Should |
| FR-3.7 | CORS habilitado para Astro dev server | Must |

### FR-4: Dashboard Astro

| Req | Descripción | Prioridad |
|-----|-------------|-----------|
| FR-4.1 | Calendar heatmap (estilo GitHub) coloreado por actividad/intensidad | Must |
| FR-4.2 | KPI cards: últimas métricas (HR reposo, HRV, Body Battery, Stress) | Must |
| FR-4.3 | Gráfica de tendencias: HR, HRV, Body Battery (rolling 30d) | Must |
| FR-4.4 | Gráfica de sueño: distribución por fases (deep/light/REM/awake) | Must |
| FR-4.5 | Tabla de actividades recientes (expandible con detalles) | Must |
| FR-4.6 | Filtro por rango de fechas (date picker) | Should |
| FR-4.7 | Responsive: mobile-first design | Must |
| FR-4.8 | Dark mode (ya existe, mantener) | Must |

## 4. Non-Functional Requirements

| Req | Descripción |
|-----|-------------|
| NFR-1 | Test coverage >80% en pipeline (sync, models, API) |
| NFR-2 | Type-safe: `mypy --strict` sin errores |
| NFR-3 | Linting: `ruff check` limpio |
| NFR-4 | Docker build <60s |
| NFR-5 | API response <200ms para queries típicas |
| NFR-6 | Dashboard LCP <2s |
| NFR-7 | SQLite DB soporta >2 años de datos sin degradación |

## 5. Technical Architecture

### Data Flow

```
Garmin Connect API
       ↓
  GarminClient (3x retry, exponential backoff)
       ↓
  Pydantic Models (validation + normalization)
       ↓
  Repository Layer (SQLite upsert)
       ↓
  SQLite DB (data/garsync.db)
       ↓
  FastAPI REST API
       ↓
  Astro Dashboard (SSG + client:visible islands)
```

### Project Structure (Target)

```
/src/garsync/
  __init__.py
  __main__.py
  cli.py              # Typer CLI (existing, extended)
  client.py            # GarminClient (existing)
  models.py            # Pydantic models (existing, extended)
  exporter.py          # JSON export (existing)
  db/
    connection.py      # SQLite connection manager
    schema.py          # Table definitions + migrations
    repository.py      # CRUD operations (upsert, query)
  api/
    main.py            # FastAPI app
    routes/
      activities.py
      biometrics.py
      sleep.py
      stats.py
      sync.py
/frontend/             # Astro project
  src/
    layouts/
      Layout.astro     # Base layout (dark mode)
    pages/
      index.astro      # Main dashboard
    components/
      Heatmap.astro    # Calendar heatmap (island)
      KpiCards.astro   # KPI summary cards
      TrendChart.astro # Tendencias (Chart.js island)
      SleepChart.astro # Sleep architecture (island)
      ActivityTable.astro # Recent activities
    lib/
      api.ts           # Fetch helpers for FastAPI
/data/                 # SQLite DB + JSON exports
/tests/                # pytest (mirrors src structure)
```

## 6. Out of Scope (V1)

- Custom training types (V2)
- Periodización (V2)
- Training Load, VO2 Max, Steps metrics (V2)
- AI chat, summaries, pattern detection (V3)
- Sync via web button or cron (V2)
- User authentication (single user, local)
- Mobile app / PWA

## 7. Success Criteria

- [ ] `poetry run garsync sync --days 30` popula SQLite con 30 días de datos
- [ ] `poetry run uvicorn garsync.api.main:app` sirve datos via REST
- [ ] Dashboard Astro en localhost muestra heatmap + métricas reales
- [ ] `make run` sincroniza + levanta API + dashboard con Docker Compose
- [ ] Tests pasan con >80% coverage
- [ ] Proyecto desplegable en Raspberry Pi con `docker compose up`
