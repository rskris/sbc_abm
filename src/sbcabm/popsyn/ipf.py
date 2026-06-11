"""N-dimensional Iterative Proportional Fitting (Deming–Stephan, 1940).

Given a non-negative seed array and one target marginal per axis, IPF scales the
array so that, when summed along every axis except *k*, it matches the target
marginal for axis *k* — for all *k* simultaneously — while preserving the seed's
cross-classified structure as closely as possible (it is the maximum-entropy /
minimum-discrimination-information solution).

This is the classic tool for fitting a joint distribution to known marginals.
Population synthesis uses the more general *list balancing* in
:mod:`sbcabm.popsyn.balancer`; IPF is provided for table fitting and validation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class IPFResult:
    fitted: np.ndarray
    iterations: int
    converged: bool
    max_change: float


def ipf(
    seed: np.ndarray,
    marginals: list[np.ndarray],
    *,
    max_iterations: int = 1000,
    tolerance: float = 1e-9,
) -> IPFResult:
    """Fit ``seed`` to one target ``marginal`` per axis.

    Parameters
    ----------
    seed:
        Non-negative array of any number of dimensions giving the prior
        cross-classified structure. Zeros are structural and stay zero.
    marginals:
        One 1-D target array per axis of ``seed``; ``marginals[k]`` must have
        length ``seed.shape[k]``. All marginals should share the same total.
    max_iterations, tolerance:
        Stop when the largest absolute change in any cell between successive
        sweeps falls below ``tolerance``, or after ``max_iterations`` sweeps.

    Returns
    -------
    IPFResult with the fitted array and convergence diagnostics.
    """
    seed = np.asarray(seed, dtype=float)
    if seed.ndim != len(marginals):
        raise ValueError(
            f"seed has {seed.ndim} dims but {len(marginals)} marginals were given"
        )
    if np.any(seed < 0):
        raise ValueError("seed must be non-negative")

    targets = [np.asarray(m, dtype=float) for m in marginals]
    for axis, target in enumerate(targets):
        if target.shape != (seed.shape[axis],):
            raise ValueError(
                f"marginal for axis {axis} has shape {target.shape}, "
                f"expected ({seed.shape[axis]},)"
            )
        if np.any(target < 0):
            raise ValueError(f"marginal for axis {axis} must be non-negative")

    totals = [float(t.sum()) for t in targets]
    if totals and max(totals) - min(totals) > 1e-6 * max(max(totals), 1.0):
        raise ValueError(f"marginal totals disagree across axes: {totals}")

    fitted = seed.copy()
    converged = False
    max_change = float("inf")
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        previous = fitted.copy()
        for axis, target in enumerate(targets):
            current = fitted.sum(axis=tuple(a for a in range(fitted.ndim) if a != axis))
            # Avoid division by zero: where the current marginal is zero the
            # target must also be zero (otherwise it is structurally unreachable).
            with np.errstate(divide="ignore", invalid="ignore"):
                factor = np.where(current > 0, target / current, 0.0)
            shape = [1] * fitted.ndim
            shape[axis] = fitted.shape[axis]
            fitted = fitted * factor.reshape(shape)

        max_change = float(np.abs(fitted - previous).max()) if fitted.size else 0.0
        if max_change < tolerance:
            converged = True
            break

    return IPFResult(
        fitted=fitted,
        iterations=iteration,
        converged=converged,
        max_change=max_change,
    )
