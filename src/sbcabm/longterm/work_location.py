"""Usual-workplace location choice (destination choice).

Each worker chooses a usual work zone by a multinomial logit over all zones,
trading off travel impedance (auto time from home) against the zone's
attractiveness (a *size term* — more jobs, more likely). This is the canonical
gravity-style destination choice:

    U(zone d | home o) = β_time · time[o, d] + β_size · ln(size_d)

with zones of zero size unavailable. Probabilities are computed once per unique
home zone (all workers there share them) and sampled per worker.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice import mnl_probabilities

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
    """Assign a workplace zone to each worker.

    ``auto_skim`` is the long-form auto skim (``origin_zone``, ``dest_zone``,
    ``time_min``). Returns a Series of chosen zone ids indexed like ``workers``
    (``NaN`` where no destination is reachable/attractive).
    """
    dest_ids = zones["zone_id"].tolist()
    size = pd.to_numeric(zones.set_index("zone_id")[size_col], errors="coerce").fillna(0.0)
    with np.errstate(divide="ignore"):
        size_term = np.log(size.where(size > 0))  # NaN where size == 0 (unavailable)

    time_matrix = auto_skim.pivot_table(
        index="origin_zone", columns="dest_zone", values="time_min", aggfunc="min"
    )

    home_zones = sorted(workers[home_zone_col].unique())
    util_rows = {}
    for origin in home_zones:
        if origin in time_matrix.index:
            times = time_matrix.reindex(columns=dest_ids).loc[origin]
        else:
            times = pd.Series(np.nan, index=dest_ids)
        utility = beta_time * times.to_numpy(dtype=float) + beta_size * size_term.reindex(
            dest_ids
        ).to_numpy(dtype=float)
        util_rows[origin] = utility

    utilities = pd.DataFrame.from_dict(util_rows, orient="index", columns=dest_ids)
    # Unavailable: zero-size destinations or missing impedance.
    availability = ~utilities.isna()
    utilities = utilities.fillna(0.0)
    probabilities = mnl_probabilities(utilities, availability=availability)

    choices = pd.Series(index=workers.index, dtype=object)
    dest_array = np.asarray(dest_ids, dtype=object)
    for origin in home_zones:
        members = workers.index[workers[home_zone_col] == origin]
        prob = probabilities.loc[origin].to_numpy(dtype=float)
        if np.isnan(prob).all():
            continue
        picks = rng.choice(len(dest_array), size=len(members), p=np.nan_to_num(prob))
        choices.loc[members] = dest_array[picks]

    logger.info("work location: assigned %d/%d workers", choices.notna().sum(), len(workers))
    return choices
