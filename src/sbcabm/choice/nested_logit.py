"""Nested-logit probabilities.

Mode choice violates the independence-of-irrelevant-alternatives assumption of
plain MNL: two transit sub-modes are closer substitutes for each other than for
driving. Nested logit groups correlated alternatives into *nests*, each with a
logsum (nesting) coefficient ``λ ∈ (0, 1]``; ``λ = 1`` collapses a nest to MNL.

For alternative ``i`` in nest ``k`` with utility ``V_i``:

    P(i | k) = exp(V_i / λ_k) / Σ_{j∈k} exp(V_j / λ_k)
    P(k)     = (Σ_{j∈k} exp(V_j / λ_k))^{λ_k} / Σ_m (…)^{λ_m}
    P(i)     = P(k) · P(i | k)

Computed in a numerically stable form (a common per-row max is factored out and
cancels across nests).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Nest:
    name: str
    coefficient: float  # logsum/nesting parameter λ ∈ (0, 1]
    alternatives: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 0 < self.coefficient <= 1:
            raise ValueError(f"nest '{self.name}' λ must be in (0, 1], got {self.coefficient}")


def validate_nests(nests: list[Nest], alternatives: list[str]) -> None:
    assigned = [alt for nest in nests for alt in nest.alternatives]
    if sorted(assigned) != sorted(alternatives):
        raise ValueError(
            "nests must partition the alternatives exactly; "
            f"got {sorted(assigned)} for alternatives {sorted(alternatives)}"
        )


def nested_logit_probabilities(
    utilities: pd.DataFrame,
    nests: list[Nest],
    *,
    availability: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Nested-logit choice probabilities from utilities and a nest structure."""
    columns = list(utilities.columns)
    validate_nests(nests, columns)

    utils = utilities
    if availability is not None:
        utils = utils.where(availability.astype(bool), other=-np.inf)
    values = utils.to_numpy(dtype=float)
    col_index = {col: i for i, col in enumerate(columns)}
    n_rows, n_alts = values.shape

    finite = np.isfinite(values)
    row_max = np.where(finite, values, -np.inf).max(axis=1)
    row_max = np.where(np.isfinite(row_max), row_max, 0.0)  # all-unavailable rows

    nest_sums = np.zeros((n_rows, len(nests)))
    nest_weight = np.zeros((n_rows, len(nests)))
    exp_terms: list[np.ndarray] = []
    nest_cols: list[list[int]] = []

    for k, nest in enumerate(nests):
        idx = [col_index[a] for a in nest.alternatives]
        sub = values[:, idx]
        scaled = np.where(np.isfinite(sub), (sub - row_max[:, None]) / nest.coefficient, -np.inf)
        a_ik = np.exp(scaled)  # exp(-inf) → 0 for unavailable alternatives
        s_k = a_ik.sum(axis=1)
        nest_sums[:, k] = s_k
        nest_weight[:, k] = np.where(s_k > 0, s_k**nest.coefficient, 0.0)
        exp_terms.append(a_ik)
        nest_cols.append(idx)

    total = nest_weight.sum(axis=1)
    safe_total = np.where(total > 0, total, 1.0)
    probs = np.zeros((n_rows, n_alts))
    for k in range(len(nests)):
        s_k = nest_sums[:, k]
        safe_s = np.where(s_k > 0, s_k, 1.0)
        p_nest = nest_weight[:, k] / safe_total  # P(k)
        p_within = exp_terms[k] / safe_s[:, None]  # P(i|k)
        probs[:, nest_cols[k]] = p_nest[:, None] * p_within

    result = pd.DataFrame(probs, index=utilities.index, columns=columns)
    result[total == 0] = np.nan  # no available alternative
    return result
