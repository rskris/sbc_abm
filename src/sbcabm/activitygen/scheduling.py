"""Tour time-of-day scheduling.

Assigns each tour a start hour, end hour, and a coarse time period. This first
implementation samples a start time and duration from purpose-specific
distributions (work tours start in the morning and last most of the day;
shopping is short and midday-skewed) — a pragmatic stand-in for a full
time-of-day choice model, which would jointly choose discrete start/end periods.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("sbcabm.activitygen.scheduling")

# Period boundaries (hours): early, AM peak, midday, PM peak, evening.
_PERIOD_BREAKS = [(0, 6, "EA"), (6, 9, "AM"), (9, 15, "MD"), (15, 18, "PM"), (18, 24, "EV")]

# purpose → (start_mean, start_sd, duration_mean, duration_sd) in hours.
_SCHEDULE = {
    "work": (8.0, 1.3, 8.5, 1.5),
    "school": (8.0, 0.8, 6.5, 1.0),
    "shopping": (13.0, 2.5, 1.2, 0.6),
    "other": (12.0, 3.5, 2.0, 1.2),
}
_DEFAULT = _SCHEDULE["other"]


def period_of(hour: float) -> str:
    for start, end, label in _PERIOD_BREAKS:
        if start <= hour < end:
            return label
    return "EV"


def schedule_tours(tours: pd.DataFrame, *, rng: np.random.Generator) -> pd.DataFrame:
    """Add ``start_hour``, ``end_hour`` and ``period`` columns to the tour table."""
    tours = tours.reset_index(drop=True).copy()
    n = len(tours)
    start = np.full(n, np.nan)
    end = np.full(n, np.nan)

    purposes = tours["purpose"].to_numpy()
    for purpose in np.unique(purposes):
        idx = np.where(purposes == purpose)[0]
        s_mean, s_sd, d_mean, d_sd = _SCHEDULE.get(purpose, _DEFAULT)
        s = np.clip(rng.normal(s_mean, s_sd, len(idx)), 5.0, 22.0)
        d = np.clip(rng.normal(d_mean, d_sd, len(idx)), 0.5, 16.0)
        e = np.clip(s + d, s + 0.5, 23.5)
        start[idx] = np.round(s * 2) / 2  # to the nearest half hour
        end[idx] = np.round(e * 2) / 2

    tours["start_hour"] = start
    tours["end_hour"] = end
    tours["period"] = [period_of(h) for h in start]
    logger.info("scheduled %d tours; period mix %s", n, tours["period"].value_counts().to_dict())
    return tours
