"""Secondary mobility choices: transit pass and telecommute frequency.

Two small person-level logit models that condition later mode and tour choices:

* **Transit pass** — whether a person holds a transit pass (binary), driven by
  carlessness, worker/student status, and age.
* **Telecommute frequency** — how often a worker works from home
  (none / some / frequent), driven by income and age.

Coefficients live in ``configs/specs/transit_pass.csv`` and
``configs/specs/telecommute.csv``.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice import mnl_simulate

logger = logging.getLogger("sbcabm.longterm.mobility")

TELECOMMUTE_LEVELS = ("tc_none", "tc_some", "tc_frequent")


def run_transit_pass(
    persons: pd.DataFrame,
    spec: pd.DataFrame,
    *,
    rng: np.random.Generator,
) -> pd.Series:
    """Choose transit-pass holding for every person (boolean Series)."""
    choosers = _person_attributes(persons)
    choices = mnl_simulate(choosers, spec, rng=rng)
    holds = choices == "pass_yes"
    logger.info("transit pass: %d of %d persons hold a pass", holds.sum(), len(persons))
    return holds


def run_telecommute(
    workers: pd.DataFrame,
    spec: pd.DataFrame,
    *,
    rng: np.random.Generator,
) -> pd.Series:
    """Choose telecommute frequency for workers (level label Series)."""
    if workers.empty:
        return pd.Series(dtype=object)
    choosers = _person_attributes(workers)
    choices = mnl_simulate(choosers, spec, rng=rng)
    logger.info("telecommute: %s", choices.value_counts().to_dict())
    return choices


def _person_attributes(persons: pd.DataFrame) -> pd.DataFrame:
    """Ensure the columns the specs reference exist and are clean."""
    choosers = persons.copy()
    for col, default in (("AGEP", 0), ("HINCP", 0.0)):
        if col not in choosers.columns:
            choosers[col] = default
        choosers[col] = pd.to_numeric(choosers[col], errors="coerce").fillna(default)
    if "auto_ownership" not in choosers.columns:
        choosers["auto_ownership"] = "cars_1"
    choosers["auto_ownership"] = choosers["auto_ownership"].fillna("cars_0")
    if "has_workplace" not in choosers.columns:
        choosers["has_workplace"] = (
            choosers["workplace_zone"].notna()
            if "workplace_zone" in choosers.columns
            else False
        )
    return choosers
