"""Multimodal network for skim building and assignment.

The supply side (MATSim-inspired) loads travelers onto a road/active network.
The first thing it produces is **skims** — zone-to-zone level-of-service
matrices (time, distance) — which are the contract the demand models consume.

This package represents the network as two tidy tables, ``network_nodes`` and
``network_links``, wrapped by :class:`Network` (a thin ``networkx`` layer). The
tables can come from OpenStreetMap (``build.from_osm``, best-effort, lazy
``osmnx``) or from any source that emits the same columns (fixtures, a custom
network).
"""

from __future__ import annotations

from .connectors import connect_zones
from .graph import Network

__all__ = ["Network", "connect_zones"]
