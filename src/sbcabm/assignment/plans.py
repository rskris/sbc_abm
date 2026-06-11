"""Agent plans and Charypar–Nagel-style scoring (story 6.3).

A *plan* is one person's day as an alternating sequence of activities and
travel legs. Scoring follows the MATSim utility structure (Charypar & Nagel
2005), simplified and documented:

* **Activities** earn utility for time spent performing them:
  ``U_act = β_perf · t_typ · ln(t / t_low)`` with ``t_low = t_typ · e⁻¹``, so an
  activity held for its typical duration earns ``β_perf · t_typ`` and very short
  activities are penalized (durations are floored at 3 minutes to keep the log
  finite).
* **Legs** cost utility in proportion to travel time:
  ``U_leg = β_mode · t_travel`` with per-mode marginal disutilities.

Scores are deterministic functions of (plans, level-of-service); travel times
come from a lookup built over the skims, preferring congested auto times when
provided.
"""

from __future__ import annotations

import logging
import math

import pandas as pd

logger = logging.getLogger("sbcabm.assignment.plans")

BETA_PERF = 6.0  # utils per hour of typical-duration activity performance
# Marginal utility of travel time, utils/hour (negative).
MODE_BETA = {
    "drive_alone": -6.0,
    "shared_ride": -6.0,
    "walk_transit": -6.0,
    "walk": -12.0,
    "bike": -10.0,
}
# Typical activity durations, hours.
TYPICAL_HOURS = {
    "home": 12.0,
    "work": 8.0,
    "school": 6.0,
    "shopping": 1.5,
    "eatout": 1.0,
    "other": 2.0,
}
_MIN_ACTIVITY_HR = 0.05  # 3-minute floor keeps ln() finite

PLAN_COLUMNS = (
    "person_id",
    "seq",
    "element",  # "activity" | "leg"
    "purpose",  # activity purpose ("" for legs)
    "mode",  # leg mode ("" for activities)
    "origin_zone",
    "dest_zone",
    "start_hour",
    "end_hour",
    "travel_min",
)


def make_time_lookup(
    skims: pd.DataFrame,
    transit_skims: pd.DataFrame | None = None,
    congested_auto: pd.DataFrame | None = None,
):
    """Build ``(origin, dest, mode) -> minutes`` over road/transit/congested LOS."""
    table: dict[tuple, float] = {}
    for row in skims.itertuples():
        key_mode = row.mode
        for mode in _modes_using(key_mode):
            table[(row.origin_zone, row.dest_zone, mode)] = float(row.time_min)
    if transit_skims is not None and not transit_skims.empty:
        for row in transit_skims.itertuples():
            table[(row.origin_zone, row.dest_zone, "walk_transit")] = float(row.total_time_min)
    if congested_auto is not None and not congested_auto.empty:
        for row in congested_auto.itertuples():
            for mode in ("drive_alone", "shared_ride"):
                table[(row.origin_zone, row.dest_zone, mode)] = float(row.time_min)

    def lookup(origin, dest, mode) -> float:
        return table.get((origin, dest, mode), 0.0)

    return lookup


def _modes_using(skim_mode: str) -> tuple[str, ...]:
    if skim_mode == "auto":
        return ("drive_alone", "shared_ride")
    if skim_mode in ("walk", "bike"):
        return (skim_mode,)
    return ()


def build_plans(trips: pd.DataFrame, time_lookup) -> pd.DataFrame:
    """Assemble each person's day plan from their ordered trips.

    The day opens with a home activity, alternates leg → activity for every
    trip (the activity at the trip's destination lasting until the next
    departure), and closes with the final activity running to hour 24.
    """
    rows = []
    ordered = trips.sort_values(["person_id", "depart_hour", "trip_id"], kind="stable")
    for person_id, person_trips in ordered.groupby("person_id", sort=False):
        seq = 0
        first = person_trips.iloc[0]
        rows.append(
            (person_id, seq, "activity", "home", "", first["origin_zone"],
             first["origin_zone"], 0.0, float(first["depart_hour"]), 0.0)
        )
        trips_list = list(person_trips.itertuples())
        for i, trip in enumerate(trips_list):
            seq += 1
            travel_min = float(time_lookup(trip.origin_zone, trip.dest_zone, trip.mode))
            arrive = float(trip.depart_hour) + travel_min / 60.0
            rows.append(
                (person_id, seq, "leg", "", trip.mode, trip.origin_zone,
                 trip.dest_zone, float(trip.depart_hour), arrive, travel_min)
            )
            seq += 1
            next_depart = (
                float(trips_list[i + 1].depart_hour) if i + 1 < len(trips_list) else 24.0
            )
            rows.append(
                (person_id, seq, "activity", trip.purpose, "", trip.dest_zone,
                 trip.dest_zone, arrive, max(next_depart, arrive), 0.0)
            )
    return pd.DataFrame(rows, columns=list(PLAN_COLUMNS))


def score_plans(plans: pd.DataFrame) -> pd.Series:
    """Charypar–Nagel-style score per person (higher is better)."""
    scores: dict = {}
    for person_id, elements in plans.groupby("person_id", sort=False):
        total = 0.0
        for el in elements.itertuples():
            if el.element == "activity":
                total += _activity_utility(el.purpose, el.end_hour - el.start_hour)
            else:
                beta = MODE_BETA.get(el.mode, -6.0)
                total += beta * el.travel_min / 60.0
        scores[person_id] = total
    result = pd.Series(scores, name="score")
    result.index.name = "person_id"
    return result


def _activity_utility(purpose: str, duration_hr: float) -> float:
    t_typ = TYPICAL_HOURS.get(purpose, TYPICAL_HOURS["other"])
    t_low = t_typ * math.exp(-1.0)
    duration = max(float(duration_hr), _MIN_ACTIVITY_HR)
    return BETA_PERF * t_typ * math.log(duration / t_low)
