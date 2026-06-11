"""Tour mode choice (nested logit).

Each tour is assigned one of five modes, grouped into nests of close
substitutes:

* **auto**: ``drive_alone``, ``shared_ride``
* **transit**: ``walk_transit``
* **active**: ``walk``, ``bike``

Utilities come from the per-tour LOS (``los.py``) via a spec
(``configs/specs/tour_mode_choice.csv``); availability gates modes by skim
reachability, walk/bike distance, and household vehicle access.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice import Nest, evaluate_utilities, nested_logit_probabilities, simulate_choices
from .los import build_mode_los

logger = logging.getLogger("sbcabm.modechoice.tour_mode")

TOUR_MODES = ("drive_alone", "shared_ride", "walk_transit", "walk", "bike")
TOUR_MODE_NESTS = [
    Nest("auto", 0.7, ("drive_alone", "shared_ride")),
    Nest("transit", 0.7, ("walk_transit",)),
    Nest("active", 0.7, ("walk", "bike")),
]

# Active modes are only plausible below these one-way times (minutes).
_MAX_WALK_MIN = 60.0
_MAX_BIKE_MIN = 75.0


def run_tour_mode_choice(
    tours: pd.DataFrame,
    households: pd.DataFrame,
    skims: pd.DataFrame,
    spec: pd.DataFrame,
    *,
    transit_skims: pd.DataFrame | None = None,
    rng: np.random.Generator,
) -> pd.Series:
    """Choose a mode for every tour. Returns a Series of mode labels."""
    los = build_mode_los(tours, skims, transit_skims)
    availability = _availability(tours, households, los)

    choosers = pd.concat(
        [tours.reset_index(drop=True), los.reset_index(drop=True).fillna(0.0)], axis=1
    )
    utilities = evaluate_utilities(choosers, spec)
    probabilities = nested_logit_probabilities(
        utilities, TOUR_MODE_NESTS, availability=availability.reset_index(drop=True)
    )
    choices = simulate_choices(probabilities, rng=rng)
    choices.index = tours.index
    logger.info("tour mode shares: %s", choices.value_counts().to_dict())
    return choices


def _availability(
    tours: pd.DataFrame, households: pd.DataFrame, los: pd.DataFrame
) -> pd.DataFrame:
    """Boolean availability per mode, aligned to ``tours``."""
    has_vehicle = _has_vehicle(tours, households)

    avail = pd.DataFrame(index=tours.index)
    auto_ok = los["auto_time"].notna()
    avail["drive_alone"] = auto_ok & has_vehicle.to_numpy()
    avail["shared_ride"] = auto_ok  # can ride as a passenger without owning a car
    avail["walk_transit"] = los["transit_time"].notna()
    avail["walk"] = los["walk_time"].notna() & (los["walk_time"] <= _MAX_WALK_MIN)
    avail["bike"] = los["bike_time"].notna() & (los["bike_time"] <= _MAX_BIKE_MIN)

    # A tour with no available mode (e.g. unreachable) falls back to shared_ride.
    none_available = ~avail.any(axis=1)
    avail.loc[none_available, "shared_ride"] = True
    return avail


def _has_vehicle(tours: pd.DataFrame, households: pd.DataFrame) -> pd.Series:
    if "auto_ownership" not in households.columns:
        return pd.Series(True, index=tours.index)
    owner = households.set_index("household_id")["auto_ownership"]
    tour_owner = tours["household_id"].map(owner)
    return (tour_owner != "cars_0").fillna(True)
