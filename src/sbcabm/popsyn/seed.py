"""Recode PUMS micro-data and build seed incidence against the controls."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .specs import ControlSpec, Recode


def apply_recodes(df: pd.DataFrame, recodes: tuple[Recode, ...]) -> pd.DataFrame:
    """Return a copy of ``df`` with one new categorical column per recode.

    Each recode maps a numeric source column into labels via inclusive bins;
    values matching no bin become ``NaN``.
    """
    out = df.copy()
    for recode in recodes:
        if recode.source not in out.columns:
            raise KeyError(f"recode source column '{recode.source}' not in frame")
        source = pd.to_numeric(out[recode.source], errors="coerce")
        labels = pd.Series(np.nan, index=out.index, dtype=object)
        for b in recode.bins:
            mask = (source >= b.low) & (source <= b.high)
            labels = labels.mask(mask, b.label)
        out[recode.target] = labels
    return out


def build_seed_incidence(
    seed_households: pd.DataFrame,
    seed_persons: pd.DataFrame,
    specs: tuple[ControlSpec, ...],
    *,
    hh_id_col: str = "seed_household_id",
) -> pd.DataFrame:
    """Build the seed-household × control incidence matrix from recoded seed data.

    Household controls contribute 1 when the household's recoded attribute equals
    the control value (or always, when ``seed_attribute`` is ``None``). Person
    controls contribute the *count* of the household's persons matching the
    control value.

    ``seed_households`` must be indexed by the seed household id;
    ``seed_persons`` must carry that id in ``hh_id_col``.
    """
    incidence = pd.DataFrame(index=seed_households.index)

    for spec in specs:
        if spec.level == "household":
            if spec.seed_attribute is None:
                incidence[spec.name] = 1.0
            else:
                if spec.seed_attribute not in seed_households.columns:
                    raise KeyError(
                        f"seed_households lacks attribute '{spec.seed_attribute}' "
                        f"for control '{spec.name}'"
                    )
                incidence[spec.name] = (
                    seed_households[spec.seed_attribute] == spec.seed_value
                ).astype(float)
        elif spec.level == "person":
            if spec.seed_attribute not in seed_persons.columns:
                raise KeyError(
                    f"seed_persons lacks attribute '{spec.seed_attribute}' "
                    f"for control '{spec.name}'"
                )
            matched = seed_persons[seed_persons[spec.seed_attribute] == spec.seed_value]
            counts = matched.groupby(hh_id_col).size()
            incidence[spec.name] = (
                counts.reindex(seed_households.index).fillna(0.0).astype(float)
            )
        else:
            raise ValueError(f"control '{spec.name}' has unknown level '{spec.level}'")

    return incidence
