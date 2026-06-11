"""Trip mode choice (conditional on the tour mode).

Each trip re-chooses its mode, but constrained to remain consistent with the
tour mode (you cannot drive a leg of a transit tour). Within that constrained
set the choice is the same nested logit used for tours, evaluated on the trip's
own origin-destination LOS — so, e.g., a drive-alone tour can have a shared-ride
leg, and a transit tour's access/egress legs can be walk.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice import evaluate_utilities, nested_logit_probabilities, simulate_choices
from .los import build_mode_los
from .tour_mode import TOUR_MODE_NESTS, _availability

logger = logging.getLogger("sbcabm.modechoice.trip_mode")

# Trip modes allowed given the tour mode (mode consistency).
_CONSISTENT = {
    "drive_alone": ("drive_alone", "shared_ride"),
    "shared_ride": ("drive_alone", "shared_ride"),
    "walk_transit": ("walk_transit", "walk"),
    "walk": ("walk",),
    "bike": ("bike",),
}


def run_trip_mode_choice(
    trips: pd.DataFrame,
    tours: pd.DataFrame,
    households: pd.DataFrame,
    skims: pd.DataFrame,
    spec: pd.DataFrame,
    *,
    transit_skims: pd.DataFrame | None = None,
    rng: np.random.Generator,
) -> pd.Series:
    """Choose a mode for every trip, consistent with its tour mode."""
    trips = trips.reset_index(drop=True)
    tour_mode = trips["tour_id"].map(tours.set_index("tour_id")["tour_mode"])

    los = build_mode_los(
        trips, skims, transit_skims, origin_col="origin_zone", dest_col="dest_zone"
    )
    availability = _availability(trips, households, los)
    availability = _restrict_to_tour_mode(availability, tour_mode)

    choosers = pd.concat([trips, los.fillna(0.0)], axis=1)
    utilities = evaluate_utilities(choosers, spec)
    probabilities = nested_logit_probabilities(
        utilities, TOUR_MODE_NESTS, availability=availability
    )
    choices = simulate_choices(probabilities, rng=rng)
    # Fall back to the tour mode for any trip with no consistent available mode.
    choices = choices.where(choices.notna(), tour_mode)
    logger.info("trip mode shares: %s", choices.value_counts().to_dict())
    return choices


def _restrict_to_tour_mode(availability: pd.DataFrame, tour_mode: pd.Series) -> pd.DataFrame:
    """Zero out modes inconsistent with each trip's tour mode."""
    restricted = availability.copy()
    tm = tour_mode.to_numpy()
    for mode in restricted.columns:
        allowed = np.array([mode in _CONSISTENT.get(t, (mode,)) for t in tm])
        restricted[mode] = restricted[mode].to_numpy() & allowed
        restricted.loc[tour_mode == mode, mode] = True  # tour's own mode always available
    return restricted
