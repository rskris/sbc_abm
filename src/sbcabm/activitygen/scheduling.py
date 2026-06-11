"""Tour time-of-day scheduling.

Assigns each tour a start hour, end hour, and a coarse time period via a
**discrete time-of-day choice**: each tour picks one ``(start, end)`` window from
an enumerated set of alternatives by a multinomial logit. The utility of a window
penalizes its squared deviation from a purpose-preferred start and duration, so
work tours peak in the morning and last most of the day while shopping is short
and midday-skewed — but every tour draws a discrete, logit-distributed schedule
rather than an independent Gaussian sample.

:func:`schedule_tours` (the sampling scheduler) is retained for reference and
quick runs; the pipeline uses :func:`choose_time_of_day`.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice import mnl_probabilities, simulate_choices

logger = logging.getLogger("sbcabm.activitygen.scheduling")

# Period boundaries (hours): early, AM peak, midday, PM peak, evening.
_PERIOD_BREAKS = [(0, 6, "EA"), (6, 9, "AM"), (9, 15, "MD"), (15, 18, "PM"), (18, 24, "EV")]

# purpose → (preferred_start, preferred_duration) hours.
_PREFERRED = {
    "work": (8.0, 8.5),
    "school": (8.0, 6.5),
    "shopping": (13.0, 1.5),
    "other": (12.0, 2.0),
}
_DEFAULT_PREF = _PREFERRED["other"]

# Sampling-scheduler parameters (legacy): (start_mean, start_sd, dur_mean, dur_sd).
_SCHEDULE = {
    "work": (8.0, 1.3, 8.5, 1.5),
    "school": (8.0, 0.8, 6.5, 1.0),
    "shopping": (13.0, 2.5, 1.2, 0.6),
    "other": (12.0, 3.5, 2.0, 1.2),
}


def period_of(hour: float) -> str:
    for start, end, label in _PERIOD_BREAKS:
        if start <= hour < end:
            return label
    return "EV"


def _alternatives() -> tuple[np.ndarray, np.ndarray]:
    """Enumerate (start, end) windows over the day; return start and end arrays."""
    starts = list(range(6, 21))  # 6:00 … 20:00
    durations = [1, 2, 3, 4, 6, 8, 10, 12]
    windows = [(s, s + d) for s in starts for d in durations if s + d <= 23]
    arr = np.array(windows, dtype=float)
    return arr[:, 0], arr[:, 1]


def choose_time_of_day(
    tours: pd.DataFrame,
    *,
    rng: np.random.Generator,
    beta_start: float = -0.30,
    beta_duration: float = -0.15,
) -> pd.DataFrame:
    """Discrete time-of-day choice; adds ``start_hour``/``end_hour``/``period``."""
    tours = tours.reset_index(drop=True).copy()
    starts, ends = _alternatives()
    durations = ends - starts
    n_alts = len(starts)

    utilities = np.zeros((len(tours), n_alts))
    purposes = tours["purpose"].to_numpy()
    for purpose in np.unique(purposes):
        pref_start, pref_dur = _PREFERRED.get(purpose, _DEFAULT_PREF)
        rows = np.where(purposes == purpose)[0]
        utilities[rows] = beta_start * (starts - pref_start) ** 2 + beta_duration * (
            durations - pref_dur
        ) ** 2

    probs = mnl_probabilities(pd.DataFrame(utilities, index=tours.index))
    chosen = simulate_choices(probs, rng=rng).to_numpy().astype(int)

    tours["start_hour"] = starts[chosen]
    tours["end_hour"] = ends[chosen]
    tours["period"] = [period_of(h) for h in tours["start_hour"]]
    logger.info(
        "time-of-day for %d tours; period mix %s",
        len(tours),
        tours["period"].value_counts().to_dict(),
    )
    return tours


def schedule_tours(tours: pd.DataFrame, *, rng: np.random.Generator) -> pd.DataFrame:
    """Sampling scheduler (legacy): draw start/duration from purpose Gaussians."""
    tours = tours.reset_index(drop=True).copy()
    n = len(tours)
    start = np.full(n, np.nan)
    end = np.full(n, np.nan)

    purposes = tours["purpose"].to_numpy()
    for purpose in np.unique(purposes):
        idx = np.where(purposes == purpose)[0]
        s_mean, s_sd, d_mean, d_sd = _SCHEDULE.get(purpose, _SCHEDULE["other"])
        s = np.clip(rng.normal(s_mean, s_sd, len(idx)), 5.0, 22.0)
        d = np.clip(rng.normal(d_mean, d_sd, len(idx)), 0.5, 16.0)
        e = np.clip(s + d, s + 0.5, 23.5)
        start[idx] = np.round(s * 2) / 2
        end[idx] = np.round(e * 2) / 2

    tours["start_hour"] = start
    tours["end_hour"] = end
    tours["period"] = [period_of(h) for h in start]
    return tours
