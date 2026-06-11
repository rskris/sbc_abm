"""Usual-workplace location choice.

A thin specialization of the shared destination-choice engine
(:func:`sbcabm.choice.destination.destination_choice`): each worker picks a usual
work zone trading auto travel time from home against the zone's employment size.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice.destination import destination_choice

logger = logging.getLogger("sbcabm.longterm.work_location")


def choose_workplace(
    workers: pd.DataFrame,
    zones: pd.DataFrame,
    auto_skim: pd.DataFrame,
    *,
    rng: np.random.Generator,
    beta_time: float = -0.03,
    beta_size: float = 1.0,
    home_zone_col: str = "zone_id",
    size_col: str = "emp_total",
) -> pd.Series:
    """Assign a workplace zone to each worker (employment as the size term)."""
    choices = destination_choice(
        workers,
        zones,
        auto_skim,
        rng=rng,
        size_col=size_col,
        beta_time=beta_time,
        beta_size=beta_size,
        origin_col=home_zone_col,
    )
    logger.info("work location: assigned %d/%d workers", choices.notna().sum(), len(workers))
    return choices
