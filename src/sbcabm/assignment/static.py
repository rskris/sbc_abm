"""Static traffic assignment: MSA-averaged all-or-nothing loading with BPR.

Auto trips are grouped by time period and origin-destination, routed along
shortest paths under *current* link times, and the resulting volumes are
averaged into the running solution with the Method of Successive Averages
(step size 1/k at iteration k). Link times are then updated with the BPR
volume-delay function

    t = t0 · (1 + α · (v / c) ** β)        (defaults α = 0.15, β = 4)

and the loop repeats until the volume pattern stabilizes. MSA with AON
sub-problems converges to user equilibrium for this fixed-demand setting.

Capacity defaults (documented per story 6.1): each directed link gets
``lanes × capacity_per_lane`` vehicles/hour, where ``capacity_per_lane`` is
1800 veh/hr and lanes default by speed class — 2 lanes where free-flow speed
≥ 50 mph, else 1 (a `lanes` column on ``network_links`` overrides this).
Per-period capacity multiplies by the period's duration in hours.

Vehicle occupancy: person-trips are converted to vehicle-trips by dividing by
a per-mode occupancy factor (default 1.0 for both auto modes, i.e. one vehicle
per person-trip). Override via the ``occupancy`` argument.

The procedure is fully deterministic — no random draws — so identical inputs
always yield identical volumes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..network.graph import Network

logger = logging.getLogger("sbcabm.assignment.static")

AUTO_MODES = ("drive_alone", "shared_ride")
DEFAULT_OCCUPANCY = {"drive_alone": 1.0, "shared_ride": 1.0}

# Period durations in hours; must match activitygen.scheduling period breaks
# (EA 0-6, AM 6-9, MD 9-15, PM 15-18, EV 18-24).
PERIOD_HOURS = {"EA": 6.0, "AM": 3.0, "MD": 6.0, "PM": 3.0, "EV": 6.0}

_CAPACITY_PER_LANE = 1800.0  # veh/hr/lane
_FAST_LANE_SPEED = 50.0  # mph at/above which a link defaults to 2 lanes


@dataclass(frozen=True)
class AssignmentResult:
    link_volumes: pd.DataFrame  # from_node, to_node, period, volume (veh/period)
    congested_times: pd.DataFrame  # from_node, to_node, period, time_min, free_flow_min
    diagnostics: pd.DataFrame  # period, iterations, relative_gap, converged, trips stats


def assign_static(
    trips: pd.DataFrame,
    network: Network,
    connectors: pd.DataFrame,
    *,
    alpha: float = 0.15,
    beta: float = 4.0,
    capacity_per_lane: float = _CAPACITY_PER_LANE,
    occupancy: dict[str, float] | None = None,
    max_iterations: int = 20,
    tolerance: float = 1e-3,
) -> AssignmentResult:
    """Assign auto trips to the drive network, period by period.

    ``trips`` must carry ``origin_zone``, ``dest_zone``, ``mode`` and
    ``depart_hour``; only :data:`AUTO_MODES` are loaded. ``connectors`` maps
    ``zone_id`` → ``node_id`` (from the ``network`` stage).
    """
    import networkx as nx

    from ..activitygen.scheduling import period_of

    occupancy = DEFAULT_OCCUPANCY if occupancy is None else occupancy

    auto = trips[trips["mode"].isin(AUTO_MODES)].copy()
    auto["period"] = [period_of(h) for h in auto["depart_hour"]]
    auto["vehicles"] = auto["mode"].map(occupancy).rdiv(1.0)  # 1 / occupancy

    zone_node = dict(zip(connectors["zone_id"], connectors["node_id"], strict=True))
    links = _directed_links(network, capacity_per_lane)
    graph = nx.DiGraph()
    for row in links.itertuples():
        graph.add_edge(row.from_node, row.to_node, time_min=row.t0)

    edge_index = {(r.from_node, r.to_node): i for i, r in enumerate(links.itertuples())}
    t0 = links["t0"].to_numpy()

    volume_frames, time_frames, diag_rows = [], [], []
    for period in sorted(auto["period"].unique()):
        sub = auto[auto["period"] == period]
        od = _od_vehicle_counts(sub, zone_node)
        capacity = links["capacity_hr"].to_numpy() * PERIOD_HOURS.get(period, 1.0)

        volumes, times, iters, gap, converged, routed = _msa_loop(
            graph, od, edge_index, t0, capacity,
            alpha=alpha, beta=beta, max_iterations=max_iterations, tolerance=tolerance,
        )

        volume_frames.append(
            links[["from_node", "to_node"]].assign(period=period, volume=volumes)
        )
        time_frames.append(
            links[["from_node", "to_node"]].assign(
                period=period, time_min=times, free_flow_min=t0
            )
        )
        diag_rows.append(
            {
                "period": period,
                "iterations": iters,
                "relative_gap": gap,
                "converged": converged,
                "trips_in_period": float(sub["vehicles"].count()),
                "vehicle_trips_routed": routed,
            }
        )

    diagnostics = pd.DataFrame(diag_rows)
    logger.info(
        "static assignment: %d periods, all converged=%s",
        len(diag_rows),
        bool(diagnostics["converged"].all()) if len(diag_rows) else True,
    )
    return AssignmentResult(
        link_volumes=pd.concat(volume_frames, ignore_index=True)
        if volume_frames
        else pd.DataFrame(columns=["from_node", "to_node", "period", "volume"]),
        congested_times=pd.concat(time_frames, ignore_index=True)
        if time_frames
        else pd.DataFrame(
            columns=["from_node", "to_node", "period", "time_min", "free_flow_min"]
        ),
        diagnostics=diagnostics,
    )


def _directed_links(network: Network, capacity_per_lane: float) -> pd.DataFrame:
    """One row per *directed* drive link with free-flow time and hourly capacity."""
    drivable = network.links[network.links["allow_drive"].astype(bool)]
    rows = []
    for link in drivable.itertuples():
        speed = float(link.speed_mph)
        t0 = link.length_mi / speed * 60.0 if speed > 0 else np.inf
        lanes = float(getattr(link, "lanes", np.nan))
        if np.isnan(lanes):
            lanes = 2.0 if speed >= _FAST_LANE_SPEED else 1.0
        cap = lanes * capacity_per_lane
        rows.append((link.from_node, link.to_node, t0, cap))
        if not bool(getattr(link, "oneway", False)):
            rows.append((link.to_node, link.from_node, t0, cap))
    return pd.DataFrame(rows, columns=["from_node", "to_node", "t0", "capacity_hr"])


def _od_vehicle_counts(trips: pd.DataFrame, zone_node: dict) -> pd.DataFrame:
    """Vehicle trips per (origin node, destination node)."""
    od = (
        trips.groupby(["origin_zone", "dest_zone"])["vehicles"].sum().reset_index()
    )
    od["src"] = od["origin_zone"].map(zone_node)
    od["dst"] = od["dest_zone"].map(zone_node)
    return od.dropna(subset=["src", "dst"])


def _msa_loop(graph, od, edge_index, t0, capacity, *, alpha, beta, max_iterations, tolerance):
    """MSA over AON sub-problems; returns volumes, times, and convergence info."""
    import networkx as nx

    n_links = len(t0)
    volumes = np.zeros(n_links)
    times = t0.copy()
    gap = float("inf")
    converged = False
    iteration = 0
    routed = 0.0

    for iteration in range(1, max_iterations + 1):
        nx.set_edge_attributes(
            graph,
            {edge: {"time_min": times[i]} for edge, i in edge_index.items()},
        )
        aux = np.zeros(n_links)
        routed = 0.0
        for src, group in od.groupby("src"):
            _, paths = nx.single_source_dijkstra(graph, src, weight="time_min")
            for row in group.itertuples():
                path = paths.get(row.dst)
                if path is None:
                    continue  # unreachable OD; reported via routed shortfall
                routed += row.vehicles
                for u, v in zip(path[:-1], path[1:], strict=True):
                    aux[edge_index[(u, v)]] += row.vehicles

        previous = volumes.copy()
        step = 1.0 / iteration
        volumes = (1.0 - step) * volumes + step * aux
        with np.errstate(divide="ignore", invalid="ignore"):
            vc = np.where(capacity > 0, volumes / capacity, 0.0)
        times = t0 * (1.0 + alpha * np.power(vc, beta))

        denom = max(float(previous.sum()), 1.0)
        gap = float(np.abs(volumes - previous).sum()) / denom
        if iteration > 1 and gap < tolerance:
            converged = True
            break

    return volumes, times, iteration, gap, converged, routed
