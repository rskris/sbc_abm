"""Fully-joint household tours.

A joint tour is a single non-mandatory excursion that several household members
make *together* (a family shopping trip, an outing). Eligible households — those
with two or more members who leave home that day — may generate one joint tour;
its participants share one destination and schedule. Each participant is emitted
as a tour row carrying a common ``joint_tour_id`` so the trip and assignment
stages treat them as travelling together.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice.destination import destination_choice

logger = logging.getLogger("sbcabm.activitygen.joint_tours")

_JOINT_PURPOSES = ("shopping", "other")
_JOINT_SIZE = {"shopping": "emp_retail", "other": "emp_service"}


def generate_joint_tours(
    persons: pd.DataFrame,
    zones: pd.DataFrame,
    auto_skim: pd.DataFrame,
    *,
    rng: np.random.Generator,
    joint_probability: float = 0.15,
    first_tour_id: int = 0,
) -> pd.DataFrame:
    """Generate joint household tours (one row per participant).

    Returns a tour table with the standard tour columns plus ``joint_tour_id``,
    ``tour_category == 'joint'``, and a pre-assigned shared ``dest_zone``.
    """
    away = persons[persons["daily_pattern"] != "home"]
    eligible = [
        (hh, group)
        for hh, group in away.groupby("household_id", sort=False)
        if len(group) >= 2
    ]

    rows = []
    joint_id = 0
    tour_id = first_tour_id
    for _, members in eligible:
        if rng.random() >= joint_probability:
            continue
        purpose = _JOINT_PURPOSES[int(rng.random() * len(_JOINT_PURPOSES))]
        for member in members.itertuples():
            rows.append(
                (
                    tour_id,
                    member.person_id,
                    member.household_id,
                    "joint",
                    purpose,
                    member.zone_id,
                    joint_id,
                )
            )
            tour_id += 1
        joint_id += 1

    columns = [
        "tour_id",
        "person_id",
        "household_id",
        "tour_category",
        "purpose",
        "home_zone",
        "joint_tour_id",
    ]
    tours = pd.DataFrame(rows, columns=columns)
    if tours.empty:
        tours["dest_zone"] = pd.Series(dtype=object)
        return tours

    tours["dest_zone"] = _shared_destinations(tours, zones, auto_skim, rng)
    logger.info("generated %d joint tours across %d households", joint_id, len(eligible))
    return tours


def _shared_destinations(tours, zones, auto_skim, rng) -> np.ndarray:
    """Choose one destination per joint tour and broadcast it to participants."""
    # One representative row per joint tour drives the destination choice.
    reps = tours.drop_duplicates("joint_tour_id").copy()
    dest_by_joint = {}
    for purpose, size_col in _JOINT_SIZE.items():
        mask = reps["purpose"] == purpose
        if not mask.any():
            continue
        col = size_col if size_col in zones.columns else "emp_total"
        chosen = destination_choice(
            reps.loc[mask], zones, auto_skim, rng=rng, size_col=col, origin_col="home_zone"
        )
        for idx in reps.loc[mask].index:
            dest_by_joint[reps.at[idx, "joint_tour_id"]] = chosen.loc[idx]
    return tours["joint_tour_id"].map(dest_by_joint).to_numpy()
