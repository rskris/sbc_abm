"""The ``assignment`` pipeline stage: static BPR loading of the trip list.

Reads ``trips``, ``network_nodes``/``network_links`` and ``zone_connectors``,
runs :func:`~sbcabm.assignment.static.assign_static`, and writes
``link_volumes``, ``congested_times`` and ``assignment_diagnostics``.
"""

from __future__ import annotations

import logging

from ..config import Config
from ..network.graph import Network
from ..pipeline import DataStore
from .static import assign_static

logger = logging.getLogger("sbcabm.assignment")

_REQUIRED = ("trips", "network_nodes", "network_links", "zone_connectors")


def run_assignment(config: Config, store: DataStore) -> None:
    missing = [name for name in _REQUIRED if not store.has(name)]
    if missing:
        raise KeyError(f"assignment requires {missing}; run earlier stages first")

    network = Network.from_tables(store.get("network_nodes"), store.get("network_links"))
    result = assign_static(store.get("trips"), network, store.get("zone_connectors"))

    store.put("link_volumes", result.link_volumes)
    store.put("congested_times", result.congested_times)
    store.put("assignment_diagnostics", result.diagnostics)
    logger.info(
        "assignment: %d link-period volumes over %d periods",
        len(result.link_volumes),
        result.diagnostics["period"].nunique() if len(result.diagnostics) else 0,
    )
