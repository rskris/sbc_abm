"""List balancing / Iterative Proportional Updating (IPU).

Population synthesis needs per-seed-household *weights* such that weighted sums
of the seed match many marginal controls at once — controls that can mix
household-level attributes (e.g. households by income) and person-level
attributes (e.g. persons by age, which a single household contributes several
of). IPF on a contingency table cannot express that; list balancing can.

Each seed household ``i`` has an *incidence* ``a[i, j]`` against control ``j`` —
the amount household ``i`` contributes to control ``j`` if selected once
(1 for "household is in category j"; an integer count for person controls). We
solve for weights ``w[i] >= 0`` so that ``sum_i a[i, j] * w[i] == control[j]``
for every ``j``, as nearly as possible, by cyclically adjusting one control at a
time — the IPU algorithm of Ye et al. (2009), the engine inside PopulationSim.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BalanceResult:
    weights: np.ndarray
    iterations: int
    converged: bool
    max_gap: float  # largest |weighted_sum - control| / control across controls
    relaxed: tuple[int, ...] = ()  # controls dropped as infeasible (no seed support)

    def weighted_totals(self, incidence: np.ndarray) -> np.ndarray:
        return incidence.T @ self.weights


def balance_weights(
    incidence: np.ndarray,
    controls: np.ndarray,
    *,
    initial_weights: np.ndarray | None = None,
    max_iterations: int = 1000,
    tolerance: float = 1e-6,
    min_weight: float = 1e-9,
    relax_infeasible: bool = False,
) -> BalanceResult:
    """Solve for seed-household weights matching marginal controls (IPU).

    Parameters
    ----------
    incidence:
        ``(n_seed, n_controls)`` non-negative array. ``incidence[i, j]`` is the
        contribution of one unit of seed household ``i`` to control ``j``.
    controls:
        ``(n_controls,)`` non-negative target totals.
    initial_weights:
        Optional ``(n_seed,)`` starting weights (e.g. PUMS expansion factors).
        Defaults to all ones.
    max_iterations:
        Maximum number of full sweeps over all controls.
    tolerance:
        Convergence threshold on the maximum relative control gap.
    min_weight:
        Weights are floored at this value to keep every seed reachable and avoid
        division/overflow issues.
    relax_infeasible:
        A control with a positive target but no contributing seed household is
        impossible to satisfy (the seed lacks that category). When ``False`` this
        raises; when ``True`` such controls are dropped from balancing and
        reported in ``BalanceResult.relaxed`` so the rest can still be matched.

    Returns
    -------
    BalanceResult with the fitted weights and convergence diagnostics.
    """
    incidence = np.asarray(incidence, dtype=float)
    controls = np.asarray(controls, dtype=float)

    if incidence.ndim != 2:
        raise ValueError("incidence must be 2-D (n_seed, n_controls)")
    n_seed, n_controls = incidence.shape
    if controls.shape != (n_controls,):
        raise ValueError(
            f"controls has shape {controls.shape}, expected ({n_controls},)"
        )
    if np.any(incidence < 0):
        raise ValueError("incidence must be non-negative")
    if np.any(controls < 0):
        raise ValueError("controls must be non-negative")

    if initial_weights is None:
        weights = np.ones(n_seed, dtype=float)
    else:
        weights = np.asarray(initial_weights, dtype=float).copy()
        if weights.shape != (n_seed,):
            raise ValueError(
                f"initial_weights has shape {weights.shape}, expected ({n_seed},)"
            )
        if np.any(weights < 0):
            raise ValueError("initial_weights must be non-negative")

    weights = np.maximum(weights, min_weight)

    # Controls that no seed can contribute to are infeasible: impossible to
    # satisfy because the seed lacks that category. Either raise or relax them.
    contributable = incidence.sum(axis=0) > 0
    infeasible = (~contributable) & (controls > 0)
    relaxed = tuple(int(j) for j in np.where(infeasible)[0])
    if relaxed and not relax_infeasible:
        raise ValueError(
            f"controls {list(relaxed)} are positive but no seed household "
            "contributes to them (pass relax_infeasible=True to drop them)"
        )
    # A control is "active" if it is feasible and has a positive target.
    active = (~infeasible) & (controls > 0)

    converged = False
    max_gap = float("inf")
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        for j in range(n_controls):
            if not active[j]:
                continue
            col = incidence[:, j]
            weighted_sum = float(col @ weights)
            if weighted_sum <= 0:
                continue
            factor = controls[j] / weighted_sum
            # General IPU update: w_i *= factor ** a_ij. For binary incidence
            # this is the familiar w_i *= factor for members of category j.
            update = np.where(col > 0, np.power(factor, col), 1.0)
            weights = np.maximum(weights * update, min_weight)

        totals = incidence.T @ weights
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(active, np.abs(totals - controls) / controls, 0.0)
        max_gap = float(rel.max()) if rel.size else 0.0
        if max_gap < tolerance:
            converged = True
            break

    return BalanceResult(
        weights=weights,
        iterations=iteration,
        converged=converged,
        max_gap=max_gap,
        relaxed=relaxed,
    )
