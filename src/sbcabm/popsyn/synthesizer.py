"""Population synthesizer.

Ties the pieces together: for each zone, balance seed-household weights to the
zone's marginal controls (IPU), integerize them to a whole number of
households, then expand the seed households (and their persons) into a concrete
synthetic population with fresh, globally-unique IDs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .balancer import balance_weights
from .integerize import integerize_weights


@dataclass(frozen=True)
class SynthesisResult:
    households: pd.DataFrame  # one row per synthetic household
    persons: pd.DataFrame  # one row per synthetic person
    diagnostics: pd.DataFrame  # per-zone convergence info

    @property
    def n_households(self) -> int:
        return len(self.households)

    @property
    def n_persons(self) -> int:
        return len(self.persons)


def build_incidence(
    seed_households: pd.DataFrame,
    *,
    household_categories: Mapping[str, pd.Series] | None = None,
    person_categories: Mapping[str, pd.Series] | None = None,
) -> pd.DataFrame:
    """Assemble a seed-household × control incidence matrix.

    Parameters
    ----------
    seed_households:
        Seed household table, indexed by seed household id. The returned
        incidence is aligned to this index.
    household_categories:
        ``control_name -> boolean Series`` over the seed-household index. The
        incidence is 1 where True (the household belongs to that category).
    person_categories:
        ``control_name -> Series`` already aggregated to the seed-household
        index giving the *number of persons* in each household matching the
        category (a household with two children contributes 2 to a
        "persons under 18" control). Missing households are treated as 0.

    Returns
    -------
    DataFrame indexed like ``seed_households``, one column per control.
    """
    incidence = pd.DataFrame(index=seed_households.index)

    for name, mask in (household_categories or {}).items():
        incidence[name] = mask.reindex(seed_households.index).fillna(False).astype(float)

    for name, counts in (person_categories or {}).items():
        incidence[name] = counts.reindex(seed_households.index).fillna(0.0).astype(float)

    return incidence


def synthesize(
    seed_households: pd.DataFrame,
    seed_persons: pd.DataFrame,
    incidence: pd.DataFrame,
    controls: pd.DataFrame,
    *,
    total_households_control: str | None = None,
    hh_id_col: str = "seed_household_id",
    person_hh_id_col: str = "seed_household_id",
    seed: int = 0,
    max_iterations: int = 2000,
    tolerance: float = 1e-4,
) -> SynthesisResult:
    """Synthesize households and persons for every zone in ``controls``.

    Parameters
    ----------
    seed_households:
        Seed households indexed by seed household id; columns are attributes to
        carry onto the synthetic households.
    seed_persons:
        Seed persons with a column (``person_hh_id_col``) linking to the seed
        household id; other columns are person attributes.
    incidence:
        Seed-household × control incidence (see :func:`build_incidence`),
        indexed identically to ``seed_households``.
    controls:
        Per-zone marginal targets: index = zone id, columns include every
        control in ``incidence`` (extra columns are ignored).
    total_households_control:
        Name of the control giving the integer household count per zone, used
        as the integerization target. If ``None``, the rounded sum of balanced
        weights is used.
    hh_id_col:
        Name of the provenance column written on synthetic households recording
        their seed household id.
    person_hh_id_col:
        Column in ``seed_persons`` linking persons to their seed household.
    seed:
        Base RNG seed; each zone draws a distinct, reproducible sub-seed.

    Returns
    -------
    SynthesisResult with ``households``, ``persons`` and ``diagnostics`` tables.
    """
    control_names = list(incidence.columns)
    missing = [c for c in control_names if c not in controls.columns]
    if missing:
        raise ValueError(f"controls is missing columns for: {missing}")
    if not incidence.index.equals(seed_households.index):
        raise ValueError("incidence and seed_households must share the same index")

    incidence_mat = incidence.to_numpy(dtype=float)
    seed_ids = seed_households.index.to_numpy()

    hh_frames: list[pd.DataFrame] = []
    diag_rows: list[dict] = []
    next_household_id = 0

    for zone_id, row in controls.iterrows():
        targets = row[control_names].to_numpy(dtype=float)

        result = balance_weights(
            incidence_mat,
            targets,
            max_iterations=max_iterations,
            tolerance=tolerance,
            relax_infeasible=True,
        )

        target_total: int | None = None
        if total_households_control is not None:
            target_total = int(round(float(row[total_households_control])))

        zone_seed = (hash((seed, zone_id)) & 0xFFFFFFFF)
        rng = np.random.default_rng(zone_seed)
        counts = integerize_weights(
            result.weights, target_total=target_total, rng=rng
        )

        diag_rows.append(
            {
                "zone_id": zone_id,
                "balance_iterations": result.iterations,
                "balance_converged": result.converged,
                "max_control_gap": result.max_gap,
                "relaxed_controls": len(result.relaxed),
                "synthesized_households": int(counts.sum()),
            }
        )

        nonzero = counts > 0
        if not nonzero.any():
            continue

        repeated_seed_ids = np.repeat(seed_ids[nonzero], counts[nonzero])
        n_new = repeated_seed_ids.size

        zone_hh = seed_households.loc[repeated_seed_ids].reset_index(drop=True)
        zone_hh.insert(0, "household_id", np.arange(next_household_id, next_household_id + n_new))
        zone_hh.insert(1, "zone_id", zone_id)
        zone_hh[hh_id_col] = repeated_seed_ids
        next_household_id += n_new
        hh_frames.append(zone_hh)

    if hh_frames:
        households = pd.concat(hh_frames, ignore_index=True)
    else:
        cols = ["household_id", "zone_id", *seed_households.columns, hh_id_col]
        households = pd.DataFrame(columns=cols)

    persons = _expand_persons(
        households,
        seed_persons,
        hh_id_col=hh_id_col,
        person_hh_id_col=person_hh_id_col,
    )

    diagnostics = pd.DataFrame(diag_rows)
    return SynthesisResult(households=households, persons=persons, diagnostics=diagnostics)


def _expand_persons(
    households: pd.DataFrame,
    seed_persons: pd.DataFrame,
    *,
    hh_id_col: str,
    person_hh_id_col: str,
) -> pd.DataFrame:
    """Replicate each synthetic household's seed persons, with fresh IDs."""
    if households.empty:
        cols = ["person_id", "household_id", "zone_id", *(
            c for c in seed_persons.columns if c != person_hh_id_col
        )]
        return pd.DataFrame(columns=cols)

    keys = households[["household_id", "zone_id", hh_id_col]]
    # Inner join on the seed household id replicates each seed person once per
    # synthetic household that came from that seed household.
    merged = keys.merge(
        seed_persons,
        left_on=hh_id_col,
        right_on=person_hh_id_col,
        how="inner",
    )
    merged = merged.sort_values("household_id", kind="stable").reset_index(drop=True)
    merged.insert(0, "person_id", np.arange(len(merged)))

    drop_cols = [hh_id_col]
    if person_hh_id_col != hh_id_col and person_hh_id_col in merged.columns:
        drop_cols.append(person_hh_id_col)
    merged = merged.drop(columns=drop_cols)
    return merged
