"""The ``network`` pipeline stage: build the multimodal network and connectors.

Builds ``network_nodes`` / ``network_links`` from OpenStreetMap (best-effort,
lazy ``osmnx``) and falls back to bundled fixtures when offline. If a zone table
with centroids is present, it ties each zone to the network (``zone_connectors``).
GTFS transit is ingested best-effort as ``transit_stops`` / ``transit_routes``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ..config import Config
from ..data.transit import load_gtfs
from ..pipeline import DataStore
from .build import from_osm
from .connectors import connect_zones
from .graph import Network

logger = logging.getLogger("sbcabm.network")


def run_network(config: Config, store: DataStore) -> None:
    nodes, links = _build_network(config)
    store.put("network_nodes", nodes)
    store.put("network_links", links)
    logger.info("network: %d nodes, %d links", len(nodes), len(links))

    if store.has("zones"):
        zones = store.get("zones")
        if {"centroid_x", "centroid_y"}.issubset(zones.columns):
            network = Network.from_tables(nodes, links)
            store.put("zone_connectors", connect_zones(network, zones))
        else:
            logger.warning("zones lack centroids; skipping centroid connectors")

    _ingest_transit(config, store)


def _build_network(config: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    if config.data.allow_network:
        try:
            place = f"{config.region.name}, California, USA"
            return from_osm(place=place)
        except Exception as exc:  # noqa: BLE001 — fall back to fixtures
            logger.warning("OSM network build failed (%s); loading fixtures", exc)
    return _network_fixtures(config)


def _network_fixtures(config: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = Path(config.paths.fixtures_dir) / "network"
    nodes_path = base / "network_nodes.csv"
    links_path = base / "network_links.csv"
    if not nodes_path.exists() or not links_path.exists():
        raise FileNotFoundError(f"network fixtures not found under {base}")
    nodes = pd.read_csv(nodes_path, dtype={"node_id": str})
    links = pd.read_csv(links_path, dtype={"from_node": str, "to_node": str})
    return nodes, links


def _ingest_transit(config: Config, store: DataStore) -> None:
    base = Path(config.paths.fixtures_dir) / "gtfs"
    if not base.exists():
        return
    try:
        gtfs = load_gtfs(base)
    except Exception as exc:  # noqa: BLE001 — transit is optional enrichment
        logger.warning("GTFS ingest failed (%s); skipping transit", exc)
        return
    store.put("transit_stops", gtfs.get("stops", pd.DataFrame()))
    store.put("transit_routes", gtfs.get("routes", pd.DataFrame()))
    logger.info(
        "transit: %d stops, %d routes",
        len(store.get("transit_stops")),
        len(store.get("transit_routes")),
    )
