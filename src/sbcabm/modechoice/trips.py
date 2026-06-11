"""Trip generation: break tours into trips with intermediate stops.

A tour decomposes into trips (legs) between successive activity locations. The
number of stops on each half-tour comes from the stop-frequency model and their
purposes from the stop-purpose model (``stops.py``); stop locations come from the
shared destination-choice engine. Trips are spread across the tour's time window;
their modes are set by trip mode choice (``trip_mode.py``). The result is the
trip list the assignment stage will load.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice.destination import destination_choice
from .stops import sample_stop_purpose

logger = logging.getLogger("sbcabm.modechoice.trips")

TRIP_COLUMNS = (
    "trip_id",
    "tour_id",
    "person_id",
    "household_id",
    "trip_num",
    "outbound",
    "origin_zone",
    "dest_zone",
    "purpose",
    "mode",
    "depart_hour",
)
_STOP_SIZE = {"shopping": "emp_retail", "other": "emp_service", "eatout": "emp_service"}


def generate_trips(
    tours: pd.DataFrame,
    zones: pd.DataFrame,
    auto_skim: pd.DataFrame,
    *,
    rng: np.random.Generator,
    stop_probability: float = 0.25,
    out_stops: np.ndarray | None = None,
    in_stops: np.ndarray | None = None,
) -> pd.DataFrame:
    """Build the trip list from scheduled, mode-assigned tours.

    ``out_stops`` / ``in_stops`` give the number of intermediate stops per
    half-tour (from the stop-frequency model); when omitted, a simple Bernoulli
    with ``stop_probability`` is used per direction.
    """
    tours = tours.reset_index(drop=True)
    n = len(tours)
    if out_stops is None:
        out_stops = (rng.random(n) < stop_probability).astype(int)
    if in_stops is None:
        in_stops = (rng.random(n) < stop_probability).astype(int)
    stop_zone = _choose_stop_locations(tours, out_stops, in_stops, zones, auto_skim, rng)

    rows = []
    trip_id = 0
    for i, tour in enumerate(tours.itertuples()):
        nodes = [(tour.home_zone, "home")]
        for slot in range(int(out_stops[i])):
            nodes.append(stop_zone[(i, "outbound", slot)])
        primary_index = len(nodes)
        nodes.append((tour.dest_zone, tour.purpose))
        for slot in range(int(in_stops[i])):
            nodes.append(stop_zone[(i, "inbound", slot)])
        nodes.append((tour.home_zone, "home"))

        legs = len(nodes) - 1
        span = max(tour.end_hour - tour.start_hour, 0.5)
        for j in range(legs):
            origin_zone = nodes[j][0]
            dest_zone, purpose = nodes[j + 1]
            depart = tour.start_hour + span * j / legs
            rows.append(
                (
                    trip_id,
                    tour.tour_id,
                    tour.person_id,
                    tour.household_id,
                    j + 1,
                    j < primary_index,
                    origin_zone,
                    dest_zone,
                    purpose,
                    tour.tour_mode,
                    round(depart * 2) / 2,
                )
            )
            trip_id += 1

    trips = pd.DataFrame(rows, columns=list(TRIP_COLUMNS))
    logger.info("generated %d trips from %d tours", len(trips), n)
    return trips


def _choose_stop_locations(tours, out_stops, in_stops, zones, auto_skim, rng) -> dict:
    """Pick a zone (and purpose) for each requested intermediate stop, batched.

    Keyed by ``(tour_row, direction, slot)`` so a half-tour may hold several
    stops. Stop purposes follow the tour purpose via :func:`sample_stop_purpose`.
    """
    requests = []
    for i in range(len(tours)):
        tour_purpose = tours.at[i, "purpose"]
        home_zone = tours.at[i, "home_zone"]
        for direction, count in (("outbound", out_stops[i]), ("inbound", in_stops[i])):
            for slot in range(int(count)):
                purpose = sample_stop_purpose(tour_purpose, rng)
                requests.append((i, direction, slot, purpose, home_zone))
    if not requests:
        return {}

    req = pd.DataFrame(
        requests, columns=["tour_row", "direction", "slot", "purpose", "zone_id"]
    )
    stop_zone: dict = {}
    for purpose in req["purpose"].unique():
        mask = req["purpose"] == purpose
        size_col = _STOP_SIZE.get(purpose, "emp_total")
        col = size_col if size_col in zones.columns else "emp_total"
        sub = req.loc[mask]
        chosen = destination_choice(
            sub, zones, auto_skim, rng=rng, size_col=col, origin_col="zone_id"
        )
        for idx in sub.index:
            key = (sub.at[idx, "tour_row"], sub.at[idx, "direction"], sub.at[idx, "slot"])
            stop_zone[key] = (chosen.loc[idx], purpose)
    return stop_zone
