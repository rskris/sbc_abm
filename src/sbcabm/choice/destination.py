"""Destination choice: a multinomial logit over zones.

A chooser at an origin zone picks a destination zone, trading travel impedance
against zone attractiveness (a *size term*). This is the shared engine behind
workplace location and tour primary-destination choice:

    U(d | origin o) = β_time · time[o, d] + β_size · ln(size_d)

Zones of zero size are unavailable. Probabilities are computed once per unique
origin (all choosers there share them) and sampled per chooser.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .logit import mnl_probabilities


def destination_choice(
    choosers: pd.DataFrame,
    zones: pd.DataFrame,
    skim: pd.DataFrame,
    *,
    rng: np.random.Generator,
    size_col: str,
    beta_time: float = -0.03,
    beta_size: float = 1.0,
    origin_col: str = "zone_id",
    zone_id_col: str = "zone_id",
    skim_origin: str = "origin_zone",
    skim_dest: str = "dest_zone",
    skim_value: str = "time_min",
) -> pd.Series:
    """Choose a destination zone for each chooser.

    ``choosers`` carries an origin zone in ``origin_col``; ``zones`` provides the
    candidate destinations and their ``size_col`` attractor; ``skim`` is the
    long-form impedance (``skim_origin``, ``skim_dest``, ``skim_value``). Returns
    a Series of chosen zone ids indexed like ``choosers`` (``NaN`` where no
    destination is reachable/attractive).
    """
    dest_ids = zones[zone_id_col].tolist()
    size = pd.to_numeric(zones.set_index(zone_id_col)[size_col], errors="coerce").fillna(0.0)
    with np.errstate(divide="ignore"):
        size_term = np.log(size.where(size > 0))  # NaN where size == 0 (unavailable)

    time_matrix = skim.pivot_table(
        index=skim_origin, columns=skim_dest, values=skim_value, aggfunc="min"
    )

    origins = sorted(choosers[origin_col].dropna().unique())
    util_rows = {}
    for origin in origins:
        if origin in time_matrix.index:
            times = time_matrix.reindex(columns=dest_ids).loc[origin]
        else:
            times = pd.Series(np.nan, index=dest_ids)
        util_rows[origin] = beta_time * times.to_numpy(dtype=float) + beta_size * (
            size_term.reindex(dest_ids).to_numpy(dtype=float)
        )

    utilities = pd.DataFrame.from_dict(util_rows, orient="index", columns=dest_ids)
    availability = ~utilities.isna()
    probabilities = mnl_probabilities(utilities.fillna(0.0), availability=availability)

    choices = pd.Series(index=choosers.index, dtype=object)
    dest_array = np.asarray(dest_ids, dtype=object)
    for origin in origins:
        members = choosers.index[choosers[origin_col] == origin]
        prob = probabilities.loc[origin].to_numpy(dtype=float)
        if np.isnan(prob).all():
            continue
        picks = rng.choice(len(dest_array), size=len(members), p=np.nan_to_num(prob))
        choices.loc[members] = dest_array[picks]
    return choices
