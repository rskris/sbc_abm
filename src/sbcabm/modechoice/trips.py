"""Trip generation: break tours into trips with intermediate stops.

A tour decomposes into trips (legs) between successive activity locations. Each
tour may gain at most one intermediate stop per direction (a simplified
stop-frequency model); stop locations come from the shared destination-choice
engine. Trips inherit the tour's mode and are spread across the tour's time
window. The result is the trip list the assignment stage will load.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice.destination import destination_choice

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
_STOP_SIZE = {"shopping": "emp_retail", "other": "emp_service"}


def generate_trips(
    tours: pd.DataFrame,
    zones: pd.DataFrame,
    auto_skim: pd.DataFrame,
    *,
    rng: np.random.Generator,
    stop_probability: float = 0.25,
) -> pd.DataFrame:
    """Build the trip list from scheduled, mode-assigned tours."""
    tours = tours.reset_index(drop=True)
    n = len(tours)
    out_stop = rng.random(n) < stop_probability
    in_stop = rng.random(n) < stop_probability
    stop_zone = _choose_stop_locations(tours, out_stop, in_stop, zones, auto_skim, rng)

    rows = []
    trip_id = 0
    for i, tour in enumerate(tours.itertuples()):
        nodes = [(tour.home_zone, "home")]
        if (i, "outbound") in stop_zone:
            nodes.append(stop_zone[(i, "outbound")])
        primary_index = len(nodes)
        nodes.append((tour.dest_zone, tour.purpose))
        if (i, "inbound") in stop_zone:
            nodes.append(stop_zone[(i, "inbound")])
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


def _choose_stop_locations(tours, out_stop, in_stop, zones, auto_skim, rng) -> dict:
    """Pick a zone (and purpose) for each requested intermediate stop, batched."""
    requests = []
    for i in range(len(tours)):
        for direction, present in (("outbound", out_stop[i]), ("inbound", in_stop[i])):
            if present:
                purpose = "shopping" if rng.random() < 0.5 else "other"
                requests.append((i, direction, purpose, tours.at[i, "home_zone"]))
    if not requests:
        return {}

    req = pd.DataFrame(requests, columns=["tour_row", "direction", "purpose", "zone_id"])
    stop_zone: dict = {}
    for purpose, size_col in _STOP_SIZE.items():
        mask = req["purpose"] == purpose
        if not mask.any():
            continue
        col = size_col if size_col in zones.columns else "emp_total"
        sub = req.loc[mask]
        chosen = destination_choice(
            sub, zones, auto_skim, rng=rng, size_col=col, origin_col="zone_id"
        )
        for idx in sub.index:
            key = (sub.at[idx, "tour_row"], sub.at[idx, "direction"])
            stop_zone[key] = (chosen.loc[idx], purpose)
    return stop_zone
