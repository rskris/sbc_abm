"""Compute zone-to-zone skims by shortest path over the network.

For each mode we build the mode's network graph, then run a single-source
shortest path (by time) from every zone's connector node. Total origin-to-
destination time and distance add the centroid-connector access/egress legs to
the in-network path. Intrazonal trips (origin == destination) fall out naturally
as access + egress with a zero in-network leg.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from ..network.graph import Network

logger = logging.getLogger("sbcabm.skims")


@dataclass(frozen=True)
class SkimMode:
    """A skimmable mode: which network it uses and how fast it travels."""

    name: str
    network_mode: str  # "drive" | "walk" | "bike"
    link_speed_mph: float | None  # None ⇒ use each link's own speed (auto)
    connector_speed_mph: float  # speed on the access/egress connector legs


DEFAULT_MODES: tuple[SkimMode, ...] = (
    SkimMode("auto", "drive", None, 25.0),
    SkimMode("walk", "walk", 3.0, 3.0),
    SkimMode("bike", "bike", 10.0, 10.0),
)


def compute_skims(
    network: Network,
    connectors: pd.DataFrame,
    *,
    modes: tuple[SkimMode, ...] = DEFAULT_MODES,
    time_periods: tuple[str, ...] = ("free_flow",),
) -> pd.DataFrame:
    """Build a long-form skim table over all zone pairs, modes and periods.

    ``connectors`` maps ``zone_id`` → ``node_id`` with a ``connector_mi`` access
    distance (see :func:`sbcabm.network.connect_zones`). Returns columns:
    ``origin_zone``, ``dest_zone``, ``mode``, ``time_period``, ``time_min``,
    ``dist_mi``. Unreachable pairs are omitted.
    """
    import networkx as nx

    zone_node = dict(zip(connectors["zone_id"], connectors["node_id"], strict=True))
    conn_mi = dict(zip(connectors["zone_id"], connectors["connector_mi"], strict=True))
    zones = list(zone_node)

    frames: list[pd.DataFrame] = []
    for mode in modes:
        graph = network.mode_graph(mode.network_mode, speed_mph=mode.link_speed_mph)
        conn_speed = mode.connector_speed_mph

        for period in time_periods:
            rows = []
            for origin in zones:
                src = zone_node[origin]
                times, paths = nx.single_source_dijkstra(graph, src, weight="time_min")
                access = conn_mi[origin] / conn_speed * 60.0
                for dest in zones:
                    dst = zone_node[dest]
                    if dst not in times:
                        continue
                    egress = conn_mi[dest] / conn_speed * 60.0
                    net_dist = _path_distance(graph, paths[dst])
                    rows.append(
                        (
                            origin,
                            dest,
                            mode.name,
                            period,
                            access + times[dst] + egress,
                            conn_mi[origin] + net_dist + conn_mi[dest],
                        )
                    )
            frames.append(
                pd.DataFrame(
                    rows,
                    columns=[
                        "origin_zone",
                        "dest_zone",
                        "mode",
                        "time_period",
                        "time_min",
                        "dist_mi",
                    ],
                )
            )

    skims = pd.concat(frames, ignore_index=True)
    logger.info(
        "computed %d skim records (%d zones × %d modes × %d periods)",
        len(skims),
        len(zones),
        len(modes),
        len(time_periods),
    )
    return skims


def _path_distance(graph, path: list) -> float:
    """Sum link miles along a node path (0 for a single-node, intrazonal path)."""
    total = 0.0
    for u, v in zip(path[:-1], path[1:], strict=True):
        total += graph[u][v]["length_mi"]
    return total
