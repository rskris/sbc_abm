"""Coordinated Daily Activity Pattern (CDAP).

Assigns each person one of three top-level day patterns:

* ``mandatory`` — has at least one mandatory activity (work or school),
* ``nonmandatory`` — no mandatory activity but travels for other purposes,
* ``home`` — stays home all day.

ActivitySim's CDAP couples household members through interaction utilities; this
first implementation is a person-level multinomial logit on age, worker status,
and seniority (a documented simplification). Coefficients live in
``configs/specs/cdap.csv``.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice import mnl_simulate

logger = logging.getLogger("sbcabm.activitygen.cdap")

CDAP_PATTERNS = ("mandatory", "nonmandatory", "home")


def run_cdap(
    persons: pd.DataFrame,
    spec: pd.DataFrame,
    *,
    rng: np.random.Generator,
) -> pd.Series:
    """Choose a daily activity pattern for every person.

    ``persons`` must carry ``AGEP``; a ``has_workplace`` flag is derived from a
    ``workplace_zone`` column when present. Returns a Series of pattern labels
    indexed like ``persons``.
    """
    choosers = persons.copy()
    if "AGEP" not in choosers.columns:
        raise KeyError("persons must carry 'AGEP' for CDAP")
    choosers["AGEP"] = pd.to_numeric(choosers["AGEP"], errors="coerce").fillna(0)
    if "workplace_zone" in choosers.columns:
        choosers["has_workplace"] = choosers["workplace_zone"].notna()
    else:
        choosers["has_workplace"] = False

    choices = mnl_simulate(choosers, spec, rng=rng)
    logger.info("CDAP patterns: %s", choices.value_counts().to_dict())
    return choices
