"""Rebuild auto skims from congested link times.

After assignment, link travel times reflect congestion. This module re-skims
the auto network using those times, per period, producing the level-of-service
the demand models should see on the next equilibrium iteration. Distances are
carried over from the free-flow skim (congestion changes times, not lengths).
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("sbcabm.skims.congested")

# Access/egress speed on centroid connectors for auto, matching DEFAULT_MODES.
_CONNECTOR_SPEED_MPH = 25.0


def congested_auto_skims(
    congested_times: pd.DataFrame,
    connectors: pd.DataFrame,
    base_auto_skim: pd.DataFrame,
) -> pd.DataFrame:
    """Skim the drive network under congested times, one set per period.

    ``congested_times`` is the assignment output (``from_node``, ``to_node``,
    ``period``, ``time_min``). Returns long-form rows
    (``origin_zone``, ``dest_zone``, ``mode='auto'``, ``time_period=<period>``,
    ``time_min``, ``dist_mi``) with distance joined from ``base_auto_skim``.
    """
    import networkx as nx

    zone_node = dict(zip(connectors["zone_id"], connectors["node_id"], strict=True))
    conn_mi = dict(zip(connectors["zone_id"], connectors["connector_mi"], strict=True))
    zones = list(zone_node)
    base_dist = {
        (o, d): v
        for o, d, v in zip(
            base_auto_skim["origin_zone"],
            base_auto_skim["dest_zone"],
            base_auto_skim["dist_mi"],
            strict=True,
        )
    }

    frames = []
    for period, sub in congested_times.groupby("period"):
        graph = nx.DiGraph()
        for row in sub.itertuples():
            graph.add_edge(row.from_node, row.to_node, time_min=float(row.time_min))

        rows = []
        for origin in zones:
            src = zone_node[origin]
            if src not in graph:
                continue
            times = nx.single_source_dijkstra_path_length(graph, src, weight="time_min")
            access = conn_mi[origin] / _CONNECTOR_SPEED_MPH * 60.0
            for dest in zones:
                dst = zone_node[dest]
                in_net = times.get(dst)
                if in_net is None and src != dst:
                    continue
                egress = conn_mi[dest] / _CONNECTOR_SPEED_MPH * 60.0
                total = access + (in_net or 0.0) + egress
                rows.append((origin, dest, "auto", period, total, base_dist.get((origin, dest))))
        frames.append(
            pd.DataFrame(
                rows,
                columns=["origin_zone", "dest_zone", "mode", "time_period", "time_min", "dist_mi"],
            )
        )

    if not frames:
        return pd.DataFrame(
            columns=["origin_zone", "dest_zone", "mode", "time_period", "time_min", "dist_mi"]
        )
    skims = pd.concat(frames, ignore_index=True)
    logger.info("rebuilt congested auto skims: %d records", len(skims))
    return skims


def collapse_to_representative(per_period: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-period congested auto skims to one representative row per OD.

    The demand stages currently consume a single auto LOS per OD; the
    representative time is the mean across periods (period-specific demand LOS
    is future work). The row is labeled ``time_period='congested'``.
    """
    if per_period.empty:
        return per_period
    rep = (
        per_period.groupby(["origin_zone", "dest_zone"], as_index=False)
        .agg(time_min=("time_min", "mean"), dist_mi=("dist_mi", "first"))
        .assign(mode="auto", time_period="congested")
    )
    return rep[["origin_zone", "dest_zone", "mode", "time_period", "time_min", "dist_mi"]]
