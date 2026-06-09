"""Auto-ownership model.

A multinomial logit over the number of household vehicles
(0 / 1 / 2 / 3+), driven by household attributes (size, income) and the
residential context (household and employment density). Coefficients live in the
spec ``configs/specs/auto_ownership.csv``; this module only assembles the
choosers and runs the engine.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice import mnl_simulate

logger = logging.getLogger("sbcabm.longterm.auto_ownership")

AUTO_OWNERSHIP_ALTS = ("cars_0", "cars_1", "cars_2", "cars_3p")
# Zone attributes joined onto households as explanatory variables.
_ZONE_ATTRS = ("hh_density", "emp_density")


def run_auto_ownership(
    households: pd.DataFrame,
    zones: pd.DataFrame,
    spec: pd.DataFrame,
    *,
    rng: np.random.Generator,
) -> pd.Series:
    """Choose a vehicle-count category for every household.

    ``households`` must have ``zone_id`` and the household attributes the spec
    references (``NP``, ``HINCP``); zone density attributes are joined from
    ``zones``. Returns a Series of alternative labels indexed like
    ``households``.
    """
    choosers = _prepare_choosers(households, zones)
    choices = mnl_simulate(choosers, spec, rng=rng)
    logger.info(
        "auto ownership: %s",
        choices.value_counts().to_dict(),
    )
    return choices


def _prepare_choosers(households: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    choosers = households.copy()

    # Defensive defaults so a missing income or group-quarters row never NaNs
    # the whole utility.
    if "HINCP" not in choosers.columns:
        choosers["HINCP"] = 0.0
    choosers["HINCP"] = pd.to_numeric(choosers["HINCP"], errors="coerce").fillna(0.0)
    if "NP" not in choosers.columns:
        raise KeyError("households must carry 'NP' (household size) for auto ownership")

    zone_cols = ["zone_id", *[c for c in _ZONE_ATTRS if c in zones.columns]]
    merged = choosers.merge(zones[zone_cols], on="zone_id", how="left")
    for attr in _ZONE_ATTRS:
        if attr not in merged.columns:
            merged[attr] = 0.0
        merged[attr] = merged[attr].fillna(0.0)
    merged.index = choosers.index
    return merged
