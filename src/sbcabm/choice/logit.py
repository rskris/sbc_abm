"""Multinomial-logit utility evaluation, probabilities, and simulation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .spec import EXPRESSION_COLUMN, alternatives

# Expressions are trusted model config, but we still evaluate them with a
# restricted namespace: a handful of safe builtins/type constructors plus numpy.
_SAFE_BUILTINS = {
    "float": float,
    "int": int,
    "bool": bool,
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
}
_SAFE_GLOBALS = {
    "__builtins__": _SAFE_BUILTINS,
    "np": np,
    "log": np.log,
    "exp": np.exp,
    "where": np.where,
}


def evaluate_utilities(
    choosers: pd.DataFrame,
    spec: pd.DataFrame,
    *,
    expr_col: str = EXPRESSION_COLUMN,
) -> pd.DataFrame:
    """Evaluate a utility spec against ``choosers``.

    Returns a DataFrame of utilities indexed like ``choosers`` with one column
    per alternative: ``U[alt] = Σ_rows coef[row, alt] · eval(expression)``.
    """
    alts = alternatives(spec, expr_col=expr_col)
    utilities = pd.DataFrame(0.0, index=choosers.index, columns=alts)
    namespace = {col: choosers[col] for col in choosers.columns}

    for _, row in spec.iterrows():
        values = _evaluate_expression(row[expr_col], choosers, namespace)
        for alt in alts:
            coef = row[alt]
            if pd.notna(coef) and coef != 0:
                utilities[alt] += coef * values
    return utilities


def _evaluate_expression(expr: str, choosers: pd.DataFrame, namespace: dict):
    expr = expr.strip()
    if expr.startswith("@"):
        return eval(expr[1:], _SAFE_GLOBALS, namespace)  # noqa: S307 — trusted spec
    if expr in choosers.columns:
        return choosers[expr]
    try:
        return float(expr)
    except ValueError as exc:
        raise ValueError(f"cannot interpret spec expression: {expr!r}") from exc


def mnl_probabilities(
    utilities: pd.DataFrame,
    *,
    availability: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Multinomial-logit choice probabilities from utilities.

    Unavailable alternatives (``availability`` False) get zero probability. A
    chooser with no available alternative yields all-``NaN`` probabilities.
    """
    utils = utilities
    if availability is not None:
        utils = utils.where(availability.astype(bool), other=-np.inf)

    # Softmax with the per-row max removed for numerical stability.
    row_max = utils.max(axis=1).replace(-np.inf, 0.0)
    exp_utils = np.exp(utils.sub(row_max, axis=0))
    exp_utils = exp_utils.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    totals = exp_utils.sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        probs = exp_utils.div(totals, axis=0)
    probs[totals == 0] = np.nan
    return probs


def simulate_choices(
    probabilities: pd.DataFrame,
    *,
    rng: np.random.Generator,
) -> pd.Series:
    """Monte-Carlo a choice per row from a probability table.

    Returns a Series of chosen alternative labels. Rows with no available
    alternative (all-``NaN``) yield ``NaN``.
    """
    alts = np.asarray(probabilities.columns)
    probs = probabilities.to_numpy(dtype=float)
    valid = ~np.isnan(probs).all(axis=1)

    draws = rng.random(len(probabilities))
    cumulative = np.cumsum(np.nan_to_num(probs), axis=1)
    # First alternative whose cumulative probability exceeds the draw.
    choice_idx = (draws[:, None] < cumulative).argmax(axis=1)

    result = np.full(len(probabilities), None, dtype=object)
    result[valid] = alts[choice_idx[valid]]
    return pd.Series(result, index=probabilities.index)


def mnl_simulate(
    choosers: pd.DataFrame,
    spec: pd.DataFrame,
    *,
    rng: np.random.Generator,
    availability: pd.DataFrame | None = None,
    expr_col: str = EXPRESSION_COLUMN,
) -> pd.Series:
    """Evaluate a spec, form MNL probabilities, and simulate a choice per chooser."""
    utilities = evaluate_utilities(choosers, spec, expr_col=expr_col)
    probabilities = mnl_probabilities(utilities, availability=availability)
    return simulate_choices(probabilities, rng=rng)
