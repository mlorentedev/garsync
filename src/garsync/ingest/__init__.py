"""Source adapters and the window they cover.

ADR-008 §1 puts one adapter per source behind a common interface (`fetch window → normalised rows +
a cursor`); this package is where that interface lives, and `window.py` is the only place that decides
which span a run is responsible for.
"""

from garsync.ingest.window import (
    CLASSES,
    TRAILING_DAYS,
    Granularity,
    SyncClass,
    Window,
    resolve_window,
)

__all__ = [
    "CLASSES",
    "TRAILING_DAYS",
    "Granularity",
    "SyncClass",
    "Window",
    "resolve_window",
]
