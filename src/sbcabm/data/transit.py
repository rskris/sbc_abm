"""GTFS transit feed ingestion.

A GTFS feed is a set of CSV tables (optionally zipped). This module reads the
core tables a travel model needs — ``stops``, ``routes``, ``trips``,
``stop_times`` — with pandas (no special dependency), and summarizes service.

Full schedule-based transit *skims* (a RAPTOR/CSA shortest-path over the
timetable) build on this and are the next supply-side step; this provides the
ingested feed and a stop/route inventory those skims will consume.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger("sbcabm.data.transit")

_CORE_TABLES = ("stops", "routes", "trips", "stop_times")
_ID_COLUMNS = {
    "stop_id": str,
    "route_id": str,
    "trip_id": str,
    "service_id": str,
    "parent_station": str,
}


def load_gtfs(path: str | Path) -> dict[str, pd.DataFrame]:
    """Load core GTFS tables from a feed directory or ``.zip``.

    Returns a dict keyed by table name (``stops``, ``routes``, ``trips``,
    ``stop_times``); a missing optional table maps to an empty frame.
    """
    path = Path(path)
    if path.is_dir():
        return {name: _read_table(path / f"{name}.txt") for name in _CORE_TABLES}
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            out = {}
            for name in _CORE_TABLES:
                member = f"{name}.txt"
                if member in names:
                    with zf.open(member) as handle:
                        out[name] = _coerce_ids(pd.read_csv(handle))
                else:
                    out[name] = pd.DataFrame()
            return out
    raise ValueError(f"GTFS path must be a directory or .zip, got {path}")


def _read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return _coerce_ids(pd.read_csv(path))


def _coerce_ids(df: pd.DataFrame) -> pd.DataFrame:
    dtypes = {c: t for c, t in _ID_COLUMNS.items() if c in df.columns}
    return df.astype(dtypes) if dtypes else df


def summarize_service(gtfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One-row summary of the feed: counts of routes, stops, trips, stop events."""
    return pd.DataFrame(
        [
            {
                "n_routes": len(gtfs.get("routes", pd.DataFrame())),
                "n_stops": len(gtfs.get("stops", pd.DataFrame())),
                "n_trips": len(gtfs.get("trips", pd.DataFrame())),
                "n_stop_times": len(gtfs.get("stop_times", pd.DataFrame())),
            }
        ]
    )
