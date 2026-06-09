"""Destination choice: a multinomial logit over zones.

A chooser at an origin zone picks a destination zone, trading travel impedance
against zone attractiveness (a *size term*). This is the shared engine behind
workplace, school, and tour primary-destination choice:

    U(d | origin o) = β_time · time[o, d] + β_size · ln(size_d)

Zones of zero size are unavailable. Probabilities are computed once per unique
origin (all choosers there share them) and sampled per chooser.

For very large alternative sets, ``sample_size`` restricts each origin to a
uniform random sample of destinations. Because the sample is uniform, every
alternative has the same inclusion probability, so the multinomial-logit
sampling correction is constant across alternatives and cancels — no correction
term is needed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def destination_choice(
    choosers: pd.DataFrame,
    zones: pd.DataFrame,
    skim: pd.DataFrame,
    *,
    rng: np.random.Generator,
    size_col: str,
    beta_time: float = -0.03,
    beta_size: float = 1.0,
    sample_size: int | None = None,
    origin_col: str = "zone_id",
    zone_id_col: str = "zone_id",
    skim_origin: str = "origin_zone",
    skim_dest: str = "dest_zone",
    skim_value: str = "time_min",
) -> pd.Series:
    """Choose a destination zone for each chooser.

    ``choosers`` carries an origin zone in ``origin_col``; ``zones`` provides the
    candidate destinations and their ``size_col`` attractor; ``skim`` is the
    long-form impedance (``skim_origin``, ``skim_dest``, ``skim_value``).
    ``sample_size`` optionally samples that many destinations per origin. Returns
    a Series of chosen zone ids indexed like ``choosers`` (``NaN`` where no
    destination is reachable/attractive).
    """
    dest_ids = np.asarray(zones[zone_id_col], dtype=object)
    n_dest = len(dest_ids)
    size = pd.to_numeric(zones.set_index(zone_id_col)[size_col], errors="coerce").fillna(0.0)
    with np.errstate(divide="ignore"):
        size_term = np.log(size.reindex(zones[zone_id_col]).where(lambda s: s > 0)).to_numpy(
            dtype=float
        )

    time_matrix = skim.pivot_table(
        index=skim_origin, columns=skim_dest, values=skim_value, aggfunc="min"
    )
    # Align the time matrix columns to the zone order once, as a numpy array.
    time_by_origin = time_matrix.reindex(columns=zones[zone_id_col].tolist())

    choices = pd.Series(index=choosers.index, dtype=object)
    use_sampling = sample_size is not None and sample_size < n_dest

    for origin in sorted(choosers[origin_col].dropna().unique()):
        members = choosers.index[choosers[origin_col] == origin]
        if origin in time_by_origin.index:
            times = time_by_origin.loc[origin].to_numpy(dtype=float)
        else:
            times = np.full(n_dest, np.nan)
        utility = beta_time * times + beta_size * size_term  # full vector over zones

        if use_sampling:
            _choose_sampled(choices, members, utility, dest_ids, n_dest, sample_size, rng)
        else:
            probabilities = _softmax(utility)
            if probabilities is None:
                continue
            picks = rng.choice(n_dest, size=len(members), p=probabilities)
            choices.loc[members] = dest_ids[picks]

    return choices


def _choose_sampled(choices, members, utility, dest_ids, n_dest, sample_size, rng) -> None:
    """Sample a destination subset *per chooser* and choose within it.

    Uniform inclusion means the MNL sampling correction is constant and cancels,
    so each chooser's choice over its own random subset is consistent with the
    full model in aggregate.
    """
    for member in members:
        candidates = rng.choice(n_dest, size=sample_size, replace=False)
        probabilities = _softmax(utility[candidates])
        if probabilities is None:
            continue
        choices.loc[member] = dest_ids[candidates[rng.choice(sample_size, p=probabilities)]]


def _softmax(utility: np.ndarray) -> np.ndarray | None:
    """Numerically stable softmax treating non-finite utilities as unavailable.

    Returns ``None`` when no alternative is available (all non-finite).
    """
    finite = np.isfinite(utility)
    if not finite.any():
        return None
    shifted = utility - utility[finite].max()
    exp = np.where(finite, np.exp(shifted), 0.0)
    total = exp.sum()
    if total <= 0:
        return None
    return exp / total
