"""Build validation targets from ACS county data (PRD OD1, resolved).

The primary validation source is the ACS itself — the same public API the
model ingests from — because it is county-specific, current, and automatable:

* **B08301** (means of transportation to work) → observed *commute* mode
  shares, compared against the model's ``mode_share_commute`` measure;
* **B08201** (household vehicles available) → observed auto-ownership shares,
  compared against ``auto_ownership_share``.

Secondary targets (regional travel *rates* such as trips/person/day) come from
published NHTS 2017 summaries, curated as data in
``configs/validation/nhts2017_targets.csv``.

Variable IDs follow the standard table structures and are covered by the
``sbcabm preflight`` scheme verification.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("sbcabm.measures.targets")

# ACS commute-mode variables → the model's mode segments.
COMMUTE_MODE_VARIABLES: dict[str, str] = {
    "B08301_003E": "drive_alone",  # car/truck/van — drove alone
    "B08301_004E": "shared_ride",  # car/truck/van — carpooled
    "B08301_010E": "walk_transit",  # public transportation (excl. taxicab)
    "B08301_019E": "walk",
    "B08301_018E": "bike",
}
# ACS household-vehicle variables → auto-ownership segments.
VEHICLE_VARIABLES: dict[str, str] = {
    "B08201_002E": "cars_0",
    "B08201_003E": "cars_1",
    "B08201_004E": "cars_2",
}
VEHICLE_3PLUS = ("B08201_005E", "B08201_006E")  # 3 and 4+ vehicles → cars_3p

#: Every ACS variable the validation targets need (preflight checks these).
VALIDATION_ACS_VARIABLES: tuple[str, ...] = tuple(
    sorted({*COMMUTE_MODE_VARIABLES, *VEHICLE_VARIABLES, *VEHICLE_3PLUS})
)


def build_acs_targets(acs: pd.DataFrame) -> pd.DataFrame:
    """Turn a county-level ACS pull into a tidy targets table.

    ``acs`` carries one (or more, summed) rows with the
    :data:`VALIDATION_ACS_VARIABLES` estimate columns. Returns rows in the
    standard targets schema (``measure, segment, observed, source``); shares
    are normalized over the segments present so they are comparable with the
    model's share measures.
    """
    sums = {
        col: pd.to_numeric(acs[col], errors="coerce").fillna(0).sum()
        for col in VALIDATION_ACS_VARIABLES
        if col in acs.columns
    }
    rows: list[tuple[str, str, float, str]] = []

    commute = {
        segment: sums.get(var, 0.0) for var, segment in COMMUTE_MODE_VARIABLES.items()
    }
    total = sum(commute.values())
    if total > 0:
        rows += [
            ("mode_share_commute", segment, count / total, "ACS B08301 (county)")
            for segment, count in commute.items()
        ]

    vehicles = {
        segment: sums.get(var, 0.0) for var, segment in VEHICLE_VARIABLES.items()
    }
    vehicles["cars_3p"] = sum(sums.get(var, 0.0) for var in VEHICLE_3PLUS)
    total = sum(vehicles.values())
    if total > 0:
        rows += [
            ("auto_ownership_share", segment, count / total, "ACS B08201 (county)")
            for segment, count in vehicles.items()
        ]

    targets = pd.DataFrame(rows, columns=["measure", "segment", "observed", "source"])
    logger.info("built %d ACS validation targets", len(targets))
    return targets
