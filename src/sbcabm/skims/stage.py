"""The ``skims`` pipeline stage: build level-of-service matrices.

Consumes ``network_nodes`` / ``network_links`` and ``zone_connectors`` (from the
``network`` stage) and writes a long-form ``skims`` table.
"""

from __future__ import annotations

import logging

from ..config import Config
from ..network.graph import Network
from ..pipeline import DataStore
from .skims import compute_skims
from .transit import build_timetable, compute_transit_skims

logger = logging.getLogger("sbcabm.skims")

_REQUIRED = ("network_nodes", "network_links", "zone_connectors")
_TRANSIT_TABLES = ("transit_stops", "transit_routes", "transit_trips", "transit_stop_times")


def run_skims(config: Config, store: DataStore) -> None:
    missing = [name for name in _REQUIRED if not store.has(name)]
    if missing:
        raise KeyError(f"skims stage requires {missing}; run 'network' first")

    network = Network.from_tables(store.get("network_nodes"), store.get("network_links"))
    skims = compute_skims(network, store.get("zone_connectors"))
    store.put("skims", skims)
    logger.info("built skims: %d records over %d modes", len(skims), skims["mode"].nunique())


def run_transit_skims(config: Config, store: DataStore) -> None:
    """Build schedule-based transit skims from the ingested GTFS feed (RAPTOR).

    Skipped (with a warning) when no GTFS feed was ingested, so the pipeline is
    robust on networks without a usable transit feed.
    """
    if not store.has("zones"):
        raise KeyError("transit_skims stage requires 'zones'; run 'zones' first")
    if not all(store.has(name) for name in _TRANSIT_TABLES):
        logger.warning("no GTFS tables in store; skipping transit skims")
        return

    zones = store.get("zones")
    if not {"centroid_x", "centroid_y"}.issubset(zones.columns):
        logger.warning("zones lack centroids; skipping transit skims")
        return

    gtfs = {
        "stops": store.get("transit_stops"),
        "routes": store.get("transit_routes"),
        "trips": store.get("transit_trips"),
        "stop_times": store.get("transit_stop_times"),
    }
    if gtfs["stop_times"].empty:
        logger.warning("GTFS feed has no stop_times; skipping transit skims")
        return

    timetable = build_timetable(gtfs)
    transit = compute_transit_skims(timetable, zones)
    store.put("transit_skims", transit)
    logger.info("built transit skims: %d records", len(transit))
