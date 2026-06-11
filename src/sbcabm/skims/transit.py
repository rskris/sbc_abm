"""Schedule-based transit routing (RAPTOR) and transit skims.

Road skims (``skims.py``) ignore timetables; transit level-of-service depends on
*when* vehicles run. This module builds a **timetable** from GTFS and routes over
it with **RAPTOR** (Round-bAsed Public Transit Optimized Router, Delling et al.
2015): an earliest-arrival, round-by-round search where round *k* corresponds to
journeys using at most *k* transit legs. Each additional round is one more
boarding (one more possible transfer).

From the routed labels we derive zone-to-zone transit skims with a full time
decomposition — access, in-vehicle, wait, transfer-walk, egress — and a transfer
count, for a given departure time.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import NamedTuple

import numpy as np
import pandas as pd

logger = logging.getLogger("sbcabm.skims.transit")

_EARTH_RADIUS_MI = 3958.8
_INF = math.inf


def parse_gtfs_time(value: str) -> int:
    """Parse a GTFS ``HH:MM:SS`` time to seconds after midnight (>24h allowed)."""
    hours, minutes, seconds = (int(part) for part in str(value).split(":"))
    return hours * 3600 + minutes * 60 + seconds


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * _EARTH_RADIUS_MI * math.asin(math.sqrt(a))


@dataclass
class Pattern:
    """A unique stop sequence and the trips that serve it.

    ``dep`` and ``arr`` are ``(n_trips, n_stops)`` second arrays, trips sorted by
    departure at the first stop.
    """

    stops: list[str]
    dep: np.ndarray
    arr: np.ndarray


@dataclass
class Timetable:
    patterns: list[Pattern]
    routes_by_stop: dict[str, list[tuple[int, int]]]  # stop → [(pattern, position)]
    transfers: dict[str, list[tuple[str, float]]]  # stop → [(other_stop, walk_sec)]
    stop_coords: dict[str, tuple[float, float]]  # stop → (lat, lon)
    stops: list[str] = field(default_factory=list)


class Label(NamedTuple):
    """Best-known way to reach a stop, with a decomposed time budget (seconds)."""

    arrival: float
    ivt: float  # accumulated in-vehicle time
    access: float  # origin access walk
    xfer_walk: float  # transfer (between-stop) walk
    boardings: int


_ORIGIN_LABEL = Label(_INF, 0.0, 0.0, 0.0, 0)


def build_timetable(
    gtfs: dict[str, pd.DataFrame],
    *,
    walk_speed_mph: float = 3.0,
    max_transfer_mi: float = 0.25,
) -> Timetable:
    """Assemble a :class:`Timetable` from core GTFS tables.

    Trips with an identical stop sequence are grouped into one pattern. Footpath
    transfers connect stops within ``max_transfer_mi`` at ``walk_speed_mph``.
    """
    stops_df = gtfs["stops"]
    stop_coords = {
        str(r.stop_id): (float(r.stop_lat), float(r.stop_lon))
        for r in stops_df.itertuples(index=False)
    }

    stop_times = gtfs["stop_times"].copy()
    stop_times["stop_id"] = stop_times["stop_id"].astype(str)
    stop_times["trip_id"] = stop_times["trip_id"].astype(str)
    stop_times["_arr"] = stop_times["arrival_time"].map(parse_gtfs_time)
    stop_times["_dep"] = stop_times["departure_time"].map(parse_gtfs_time)
    stop_times = stop_times.sort_values(["trip_id", "stop_sequence"])

    # Group each trip's ordered stops, then bucket trips by identical sequence.
    pattern_trips: dict[tuple[str, ...], list[tuple[list[int], list[int]]]] = {}
    for _, trip in stop_times.groupby("trip_id", sort=False):
        seq = tuple(trip["stop_id"].tolist())
        pattern_trips.setdefault(seq, []).append(
            (trip["_dep"].tolist(), trip["_arr"].tolist())
        )

    patterns: list[Pattern] = []
    routes_by_stop: dict[str, list[tuple[int, int]]] = {}
    for seq, trips in pattern_trips.items():
        dep = np.array([t[0] for t in trips], dtype=float)
        arr = np.array([t[1] for t in trips], dtype=float)
        order = np.argsort(dep[:, 0])
        pattern = Pattern(list(seq), dep[order], arr[order])
        pidx = len(patterns)
        patterns.append(pattern)
        for position, stop in enumerate(seq):
            routes_by_stop.setdefault(stop, []).append((pidx, position))

    transfers = _build_transfers(stop_coords, walk_speed_mph, max_transfer_mi)
    logger.info(
        "built timetable: %d patterns, %d stops, %d transfer footpaths",
        len(patterns),
        len(stop_coords),
        sum(len(v) for v in transfers.values()),
    )
    return Timetable(
        patterns=patterns,
        routes_by_stop=routes_by_stop,
        transfers=transfers,
        stop_coords=stop_coords,
        stops=list(stop_coords),
    )


def _build_transfers(
    stop_coords: dict[str, tuple[float, float]],
    walk_speed_mph: float,
    max_transfer_mi: float,
) -> dict[str, list[tuple[str, float]]]:
    ids = list(stop_coords)
    coords = np.array([stop_coords[s] for s in ids], dtype=float)
    transfers: dict[str, list[tuple[str, float]]] = {s: [] for s in ids}
    for i, sid in enumerate(ids):
        for j in range(len(ids)):
            if i == j:
                continue
            d = haversine_mi(coords[i, 0], coords[i, 1], coords[j, 0], coords[j, 1])
            if d <= max_transfer_mi:
                transfers[sid].append((ids[j], d / walk_speed_mph * 3600.0))
    return transfers


def _earliest_trip(pattern: Pattern, position: int, ready_at: float) -> int | None:
    """Index of the earliest trip departing ``position`` at or after ``ready_at``."""
    deps = pattern.dep[:, position]
    feasible = deps >= ready_at
    if not feasible.any():
        return None
    return int(np.argmin(np.where(feasible, deps, _INF)))


def raptor(
    timetable: Timetable,
    sources: dict[str, tuple[float, float]],
    *,
    max_rounds: int = 4,
) -> dict[str, Label]:
    """Earliest-arrival RAPTOR from access stops.

    ``sources`` maps an access stop to ``(arrival_seconds, access_walk_seconds)``
    — the time the traveler reaches that stop and the access walk it took.
    Returns the best :class:`Label` per reachable stop.
    """
    best: dict[str, Label] = {}
    for stop, (arrival, access) in sources.items():
        best[stop] = Label(arrival, 0.0, access, 0.0, 0)

    marked = set(sources)
    _relax_transfers(timetable, best, marked)  # walk between nearby access stops

    for _ in range(max_rounds):
        prev = dict(best)  # boarding decisions use the previous round's arrivals
        scan = _routes_to_scan(timetable, marked)
        marked = set()

        for pidx, start in scan.items():
            pattern = timetable.patterns[pidx]
            trip: int | None = None
            board: Label | None = None
            board_pos = 0
            for pos in range(start, len(pattern.stops)):
                stop = pattern.stops[pos]
                if trip is not None:
                    arrival = pattern.arr[trip, pos]
                    if arrival < best.get(stop, _ORIGIN_LABEL).arrival:
                        best[stop] = Label(
                            arrival,
                            board.ivt + (arrival - pattern.dep[trip, board_pos]),
                            board.access,
                            board.xfer_walk,
                            board.boardings + 1,
                        )
                        marked.add(stop)
                # Can we (re)board an earlier trip here, using last round's arrival?
                pl = prev.get(stop)
                if pl is not None:
                    candidate = _earliest_trip(pattern, pos, pl.arrival)
                    if candidate is not None and (
                        trip is None
                        or pattern.dep[candidate, pos] < pattern.dep[trip, pos]
                    ):
                        trip, board, board_pos = candidate, pl, pos

        if not marked:
            break
        _relax_transfers(timetable, best, marked)

    return best


def _routes_to_scan(timetable: Timetable, marked: set[str]) -> dict[int, int]:
    """For each pattern touching a marked stop, the earliest marked position."""
    scan: dict[int, int] = {}
    for stop in marked:
        for pidx, position in timetable.routes_by_stop.get(stop, []):
            if pidx not in scan or position < scan[pidx]:
                scan[pidx] = position
    return scan


def _relax_transfers(timetable: Timetable, best: dict[str, Label], marked: set[str]) -> None:
    """Walk from each just-improved stop to nearby stops (adds transfer walk)."""
    for stop in list(marked):
        label = best[stop]
        for neighbor, walk_sec in timetable.transfers.get(stop, []):
            candidate = label.arrival + walk_sec
            if candidate < best.get(neighbor, _ORIGIN_LABEL).arrival:
                best[neighbor] = Label(
                    candidate, label.ivt, label.access, label.xfer_walk + walk_sec, label.boardings
                )
                marked.add(neighbor)


def _zone_access_stops(
    zones: pd.DataFrame,
    timetable: Timetable,
    *,
    walk_speed_mph: float,
    max_access_mi: float,
) -> dict[object, list[tuple[str, float]]]:
    """For each zone, the stops within walking distance and the walk time (sec)."""
    access: dict[object, list[tuple[str, float]]] = {}
    for row in zones.itertuples(index=False):
        zlat, zlon = float(row.centroid_y), float(row.centroid_x)
        reachable = []
        for stop, (slat, slon) in timetable.stop_coords.items():
            d = haversine_mi(zlat, zlon, slat, slon)
            if d <= max_access_mi:
                reachable.append((stop, d / walk_speed_mph * 3600.0))
        access[row.zone_id] = reachable
    return access


def compute_transit_skims(
    timetable: Timetable,
    zones: pd.DataFrame,
    *,
    departure_sec: int = 8 * 3600,
    time_period: str = "AM",
    walk_speed_mph: float = 3.0,
    max_access_mi: float = 0.5,
    max_rounds: int = 4,
) -> pd.DataFrame:
    """Zone-to-zone transit skims for a single departure time.

    Returns long-form rows (mode ``transit``) with total time and its
    decomposition (access / in-vehicle / wait / transfer-walk / egress, minutes)
    plus ``n_transfers``. Pairs with no transit path are omitted.
    """
    required = {"zone_id", "centroid_x", "centroid_y"}
    missing = required - set(zones.columns)
    if missing:
        raise ValueError(f"zones is missing centroid columns: {sorted(missing)}")

    access = _zone_access_stops(
        zones, timetable, walk_speed_mph=walk_speed_mph, max_access_mi=max_access_mi
    )

    rows = []
    for origin in zones["zone_id"]:
        origin_stops = access[origin]
        if not origin_stops:
            continue
        sources = {
            stop: (departure_sec + walk_sec, walk_sec) for stop, walk_sec in origin_stops
        }
        labels = raptor(timetable, sources, max_rounds=max_rounds)

        for dest in zones["zone_id"]:
            best = _best_egress(labels, access[dest])
            if best is None:
                continue
            label, egress_sec, arrival = best
            total = (arrival - departure_sec) / 60.0
            access_min = label.access / 60.0
            egress_min = egress_sec / 60.0
            ivt_min = label.ivt / 60.0
            xfer_min = label.xfer_walk / 60.0
            wait_min = max(total - access_min - egress_min - ivt_min - xfer_min, 0.0)
            rows.append(
                (
                    origin,
                    dest,
                    "transit",
                    time_period,
                    total,
                    access_min,
                    egress_min,
                    ivt_min,
                    wait_min,
                    xfer_min,
                    label.boardings - 1,
                )
            )

    skims = pd.DataFrame(
        rows,
        columns=[
            "origin_zone",
            "dest_zone",
            "mode",
            "time_period",
            "total_time_min",
            "access_min",
            "egress_min",
            "ivt_min",
            "wait_min",
            "xfer_walk_min",
            "n_transfers",
        ],
    )
    logger.info("computed %d transit skim records", len(skims))
    return skims


def _best_egress(
    labels: dict[str, Label], dest_stops: list[tuple[str, float]]
) -> tuple[Label, float, float] | None:
    """Pick the egress stop giving the earliest door arrival (must use transit)."""
    best: tuple[Label, float, float] | None = None
    for stop, egress_sec in dest_stops:
        label = labels.get(stop)
        if label is None or label.boardings < 1:
            continue
        arrival = label.arrival + egress_sec
        if best is None or arrival < best[2]:
            best = (label, egress_sec, arrival)
    return best
