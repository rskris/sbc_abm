"""Tour frequency, tour generation, and primary-destination choice.

A *tour* is a home-based excursion for a primary purpose. Mandatory-pattern
persons make one mandatory tour (work or school); everyone who leaves home may
make non-mandatory tours (shopping / other), whose count is a small MNL. Each
tour then gets a primary destination via the shared destination-choice engine.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice import mnl_simulate
from ..choice.destination import destination_choice

logger = logging.getLogger("sbcabm.activitygen.tours")

_NM_ALTS = ("nm_0", "nm_1", "nm_2")
_NM_COUNT = {"nm_0": 0, "nm_1": 1, "nm_2": 2}
# Non-mandatory purpose → the zone size term that attracts it.
_PURPOSE_SIZE = {
    "school": "emp_education",
    "shopping": "emp_retail",
    "other": "emp_service",
}
TOUR_COLUMNS = (
    "tour_id",
    "person_id",
    "household_id",
    "tour_category",
    "purpose",
    "home_zone",
)


def run_nonmandatory_frequency(
    persons: pd.DataFrame,
    spec: pd.DataFrame,
    *,
    rng: np.random.Generator,
) -> pd.Series:
    """Number of non-mandatory tours (0/1/2) per person.

    ``home``-pattern persons make none; ``nonmandatory``-pattern persons make at
    least one (``nm_0`` is unavailable for them). Returns an integer Series
    indexed like ``persons``.
    """
    counts = pd.Series(0, index=persons.index, dtype="int64")
    active = persons[persons["daily_pattern"] != "home"]
    if active.empty:
        return counts

    availability = pd.DataFrame(True, index=active.index, columns=list(_NM_ALTS))
    availability["nm_0"] = (active["daily_pattern"] != "nonmandatory").to_numpy()

    choices = mnl_simulate(active, spec, rng=rng, availability=availability)
    counts.loc[active.index] = choices.map(_NM_COUNT).fillna(0).astype(int).to_numpy()
    logger.info("non-mandatory tour counts: %s", counts.value_counts().to_dict())
    return counts


def generate_tours(
    persons: pd.DataFrame,
    nm_counts: pd.Series,
    *,
    rng: np.random.Generator,
    shopping_share: float = 0.4,
) -> pd.DataFrame:
    """Materialize the tour list from patterns and non-mandatory counts."""
    rows = []
    tour_id = 0
    for person in persons.itertuples(index=True):
        if person.daily_pattern == "mandatory":
            has_work = pd.notna(getattr(person, "workplace_zone", np.nan))
            purpose = "work" if has_work else "school"
            rows.append(
                (
                    tour_id,
                    person.person_id,
                    person.household_id,
                    "mandatory",
                    purpose,
                    person.zone_id,
                )
            )
            tour_id += 1

        for _ in range(int(nm_counts.loc[person.Index])):
            purpose = "shopping" if rng.random() < shopping_share else "other"
            rows.append(
                (
                    tour_id,
                    person.person_id,
                    person.household_id,
                    "nonmandatory",
                    purpose,
                    person.zone_id,
                )
            )
            tour_id += 1

    tours = pd.DataFrame(rows, columns=list(TOUR_COLUMNS))
    logger.info(
        "generated %d tours (%s)", len(tours), tours["purpose"].value_counts().to_dict()
    )
    return tours


def assign_destinations(
    tours: pd.DataFrame,
    persons: pd.DataFrame,
    zones: pd.DataFrame,
    auto_skim: pd.DataFrame,
    *,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Choose a primary destination zone for every tour.

    Work tours go to the person's usual workplace; other purposes use
    destination choice with a purpose-appropriate employment size term (falling
    back to total employment where a category is unavailable).
    """
    tours = tours.reset_index(drop=True).copy()
    if "dest_zone" not in tours.columns:
        tours["dest_zone"] = pd.NA  # preserve any pre-assigned destinations (joint tours)

    # Mandatory tours go to the person's usual location (work or school).
    by_person = persons.set_index("person_id")
    for purpose, usual_col in (("work", "workplace_zone"), ("school", "school_zone")):
        if usual_col not in persons.columns:
            continue
        mask = (tours["purpose"] == purpose) & tours["dest_zone"].isna()
        if mask.any():
            usual = by_person[usual_col]
            tours.loc[mask, "dest_zone"] = tours.loc[mask, "person_id"].map(usual).to_numpy()

    for purpose, size_col in _PURPOSE_SIZE.items():
        mask = tours["purpose"] == purpose
        # School handled above when a usual school zone exists; only choose for
        # tours still missing a destination.
        mask &= tours["dest_zone"].isna()
        if not mask.any():
            continue
        col = size_col if size_col in zones.columns else "emp_total"
        chosen = destination_choice(
            tours.loc[mask], zones, auto_skim, rng=rng, size_col=col, origin_col="home_zone"
        )
        tours.loc[mask, "dest_zone"] = chosen.to_numpy()

    # Any unresolved destination (e.g. a work tour with no workplace) stays home.
    tours["dest_zone"] = tours["dest_zone"].fillna(tours["home_zone"])
    return tours
