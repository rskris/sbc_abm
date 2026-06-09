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

logger = logging.getLogger("sbcabm.skims")

_REQUIRED = ("network_nodes", "network_links", "zone_connectors")


def run_skims(config: Config, store: DataStore) -> None:
    missing = [name for name in _REQUIRED if not store.has(name)]
    if missing:
        raise KeyError(f"skims stage requires {missing}; run 'network' first")

    network = Network.from_tables(store.get("network_nodes"), store.get("network_links"))
    skims = compute_skims(network, store.get("zone_connectors"))
    store.put("skims", skims)
    logger.info("built skims: %d records over %d modes", len(skims), skims["mode"].nunique())
