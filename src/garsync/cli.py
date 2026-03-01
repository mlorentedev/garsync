import datetime
import json
import logging
import sys
from typing import Any, Optional

import typer
from rich.console import Console
from rich.logging import RichHandler

from garsync.client import GarminClient
from garsync.exporter import JSONExporter
from garsync.models import DailyBiometrics, NormalizedActivity, SleepData, SyncResult

app = typer.Typer(help="Garmin Connect Data Extraction CLI")
console = Console()


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console, show_time=False)],
    )


def _activity_to_row(a: NormalizedActivity) -> dict[str, Any]:
    """Convert a NormalizedActivity to a dict for DB upsert."""
    return {
        "activity_id": a.activity_id,
        "activity_name": a.activity_name,
        "activity_type": a.activity_type,
        "start_time": a.start_time.isoformat(),
        "duration_seconds": a.duration_seconds,
        "distance_meters": a.distance_meters,
        "average_heart_rate": a.average_heart_rate,
        "max_heart_rate": a.max_heart_rate,
        "calories": a.calories,
        "raw_data": json.dumps(a.raw_data, default=str),
    }


def _biometrics_to_row(b: DailyBiometrics) -> dict[str, Any]:
    """Convert DailyBiometrics to a dict for DB upsert."""
    return {
        "date": b.date.isoformat(),
        "resting_heart_rate": b.resting_heart_rate,
        "hrv_balance": b.hrv_balance,
        "body_battery_highest": b.body_battery_highest,
        "body_battery_lowest": b.body_battery_lowest,
        "stress_average": b.stress_average,
        "raw_data": json.dumps(b.raw_data, default=str),
    }


def _sleep_to_row(s: SleepData) -> dict[str, Any]:
    """Convert SleepData to a dict for DB upsert."""
    return {
        "date": s.date.isoformat(),
        "sleep_start": s.sleep_start.isoformat() if s.sleep_start else None,
        "sleep_end": s.sleep_end.isoformat() if s.sleep_end else None,
        "total_sleep_seconds": s.total_sleep_seconds,
        "deep_sleep_seconds": s.deep_sleep_seconds,
        "light_sleep_seconds": s.light_sleep_seconds,
        "rem_sleep_seconds": s.rem_sleep_seconds,
        "awake_sleep_seconds": s.awake_sleep_seconds,
        "sleep_score": s.sleep_score,
        "raw_data": json.dumps(s.raw_data, default=str),
    }


def _dates_to_sync(
    days: int,
    full: bool,
    latest_date: Optional[str],
) -> list[datetime.date]:
    """Compute which dates need syncing.

    Incremental: only dates after latest_date (always re-fetch today).
    Full or no latest_date: fetch all requested days.
    """
    today = datetime.date.today()
    all_dates = [today - datetime.timedelta(days=i) for i in range(days)]

    if full or latest_date is None:
        return all_dates

    cutoff = datetime.date.fromisoformat(latest_date)
    return [d for d in all_dates if d >= cutoff]


@app.command()
def sync(
    email: str = typer.Option(..., envvar="GARMIN_EMAIL", help="Garmin Connect Email"),
    password: str = typer.Option(..., envvar="GARMIN_PASSWORD", help="Garmin Connect Password"),
    days: int = typer.Option(1, help="Number of past days to sync"),
    activities_limit: int = typer.Option(10, help="Maximum number of recent activities to fetch"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output JSON file. Defaults to stdout."
    ),
    db: Optional[str] = typer.Option(
        None, "--db", help="SQLite database path for persistent storage."
    ),
    full: bool = typer.Option(False, "--full", help="Force full sync (ignore incremental state)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Synchronize data from Garmin Connect."""
    setup_logging(verbose)
    logger = logging.getLogger("garsync")

    client = GarminClient(email=email, password=password)
    result = SyncResult()

    conn = None
    if db:
        from garsync.db import (
            ActivityRepository,
            BiometricsRepository,
            SleepRepository,
            SyncLogRepository,
            get_connection,
            init_db,
        )

        conn = get_connection(db)
        init_db(conn)
        activity_repo = ActivityRepository(conn)
        bio_repo = BiometricsRepository(conn)
        sleep_repo = SleepRepository(conn)
        sync_log = SyncLogRepository(conn)
        logger.info(f"Using SQLite database: {db}")

    try:
        client.login()

        # --- Activities (always fetch latest N, upsert by ID) ---
        if activities_limit > 0:
            result.activities = client.fetch_activities(start=0, limit=activities_limit)
            logger.info(f"Fetched {len(result.activities)} activities")
            if conn:
                rows = [_activity_to_row(a) for a in result.activities]
                activity_repo.upsert_batch(rows)
                sync_log.log("activities", records_synced=len(rows))
                logger.info(f"Persisted {len(rows)} activities to DB")

        # --- Daily Data (Biometrics & Sleep) ---
        if conn:
            bio_dates = _dates_to_sync(days, full, bio_repo.get_latest_date())
            sleep_dates = _dates_to_sync(days, full, sleep_repo.get_latest_date())
            all_dates = sorted(set(bio_dates + sleep_dates), reverse=True)
        else:
            today = datetime.date.today()
            all_dates = [today - datetime.timedelta(days=i) for i in range(days)]

        bio_count = 0
        sleep_count = 0
        for target_date in all_dates:
            try:
                bio = client.fetch_biometrics(target_date)
                result.biometrics.append(bio)
                if conn:
                    bio_repo.upsert(_biometrics_to_row(bio))
                    bio_count += 1
            except Exception as e:
                logger.warning(f"Failed biometrics for {target_date}: {e}")
                if conn:
                    sync_log.log("biometrics", 0, "error", str(e))

            try:
                sleep = client.fetch_sleep(target_date)
                result.sleep.append(sleep)
                if conn:
                    sleep_repo.upsert(_sleep_to_row(sleep))
                    sleep_count += 1
            except Exception as e:
                logger.warning(f"Failed sleep for {target_date}: {e}")
                if conn:
                    sync_log.log("sleep", 0, "error", str(e))

        if conn:
            sync_log.log("biometrics", records_synced=bio_count)
            sync_log.log("sleep", records_synced=sleep_count)
            logger.info(f"Synced {bio_count} biometrics + {sleep_count} sleep days to DB")

        # --- JSON Export (backward compatible) ---
        if output:
            with open(output, "w") as f:
                JSONExporter.export(result, f)
            logger.info(f"Data saved to {output}")
        elif not db:
            JSONExporter.export(result, sys.stdout)

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        if conn:
            sync_log.log("sync", 0, "error", str(e))
        raise typer.Exit(code=1)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    app()
