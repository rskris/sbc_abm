"""Usual-school location choice.

The school-location analogue of workplace choice: each student picks a usual
school zone by destination choice, trading auto travel time from home against a
zone's enrollment attractiveness. With no enrollment table ingested yet, we use
education-sector employment (LODES ``emp_education``) as the size term, falling
back to total employment where that is unavailable.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice.destination import destination_choice

logger = logging.getLogger("sbcabm.longterm.school_location")

_PREFERRED_SIZE = "emp_education"
_FALLBACK_SIZE = "emp_total"


def choose_school(
    students: pd.DataFrame,
    zones: pd.DataFrame,
    auto_skim: pd.DataFrame,
    *,
    rng: np.random.Generator,
    beta_time: float = -0.02,
    beta_size: float = 1.0,
    home_zone_col: str = "zone_id",
) -> pd.Series:
    """Assign a school zone to each student.

    Uses ``emp_education`` as the size term when it is present and non-zero,
    otherwise total employment.
    """
    size_col = _choose_size_column(zones)
    choices = destination_choice(
        students,
        zones,
        auto_skim,
        rng=rng,
        size_col=size_col,
        beta_time=beta_time,
        beta_size=beta_size,
        origin_col=home_zone_col,
    )
    logger.info(
        "school location: assigned %d/%d students (size=%s)",
        choices.notna().sum(),
        len(students),
        size_col,
    )
    return choices


def _choose_size_column(zones: pd.DataFrame) -> str:
    if _PREFERRED_SIZE in zones.columns:
        total = pd.to_numeric(zones[_PREFERRED_SIZE], errors="coerce").fillna(0.0).sum()
        if total > 0:
            return _PREFERRED_SIZE
    return _FALLBACK_SIZE
