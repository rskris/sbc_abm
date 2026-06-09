"""Integerization of fractional synthesis weights.

List balancing yields *fractional* household weights. A synthetic population
needs a whole number of copies of each seed household. We round so that:

* every count is a non-negative integer,
* the counts sum exactly to a target total (the household control), and
* the rounded counts stay as close as possible to the fractional weights.

This is the classic *largest-remainder* (Hamilton) apportionment: floor every
weight, then hand out the remaining units to the households with the largest
fractional parts. Ties are broken deterministically using a seeded RNG so runs
are reproducible.
"""

from __future__ import annotations

import numpy as np


def integerize_weights(
    weights: np.ndarray,
    *,
    target_total: int | None = None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Convert fractional weights to integer counts summing to a target.

    Parameters
    ----------
    weights:
        ``(n_seed,)`` non-negative fractional weights.
    target_total:
        Desired integer sum of the result. Defaults to the rounded sum of
        ``weights`` (the natural total implied by the balanced weights).
    rng:
        Optional seeded generator for deterministic tie-breaking.

    Returns
    -------
    Integer array of the same shape as ``weights`` summing to ``target_total``.
    """
    weights = np.asarray(weights, dtype=float)
    if weights.ndim != 1:
        raise ValueError("weights must be 1-D")
    if np.any(weights < 0):
        raise ValueError("weights must be non-negative")

    if target_total is None:
        target_total = int(round(float(weights.sum())))
    if target_total < 0:
        raise ValueError("target_total must be non-negative")

    n = weights.size
    if n == 0:
        if target_total != 0:
            raise ValueError("cannot reach a positive target with no weights")
        return np.zeros(0, dtype=np.int64)

    floor = np.floor(weights).astype(np.int64)
    fractional = weights - floor
    result = floor.copy()
    remainder = int(target_total - floor.sum())

    if remainder == 0:
        return result

    if remainder > 0:
        # Hand out `remainder` extra units to the largest fractional parts. If
        # the target far exceeds the floor sum (sparse weights), give every cell
        # an equal base share first, then allocate the leftover by remainder.
        if remainder >= n:
            base, remainder = divmod(remainder, n)
            result += base
        order = _stable_order(fractional, rng, ascending=False)
        for idx in order[:remainder]:
            result[idx] += 1
        return result

    # remainder < 0: remove `to_remove` units, preferring the smallest
    # fractional parts, cycling so we only ever decrement cells above zero.
    to_remove = -remainder
    order = _stable_order(fractional, rng, ascending=True)
    pos = 0
    while to_remove > 0:
        idx = order[pos % n]
        if result[idx] > 0:
            result[idx] -= 1
            to_remove -= 1
        pos += 1
    return result


def _stable_order(
    values: np.ndarray, rng: np.random.Generator | None, *, ascending: bool
) -> np.ndarray:
    """Order indices by ``values`` with seeded, deterministic tie-breaking."""
    if rng is None:
        rng = np.random.default_rng(0)
    jitter = rng.random(values.shape) * 1e-12
    keyed = values + jitter
    order = np.argsort(keyed, kind="stable")
    if not ascending:
        order = order[::-1]
    return order
