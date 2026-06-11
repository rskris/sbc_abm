"""Iterative ASC calibration toward observed shares (story 7.3).

The classic procedure for matching a logit model's aggregate shares to targets:
adjust each alternative's alternative-specific constant by the damped log ratio
of target to modeled share,

    ASC_a ← ASC_a + damping · ln(target_a / modeled_a)

holding a base alternative fixed (its ASC stays 0 to anchor the scale), until
every share is within tolerance. The original (estimated) spec is never
overwritten — calibrated specs are written alongside with a ``.calibrated``
suffix.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from pathlib import Path

import pandas as pd

logger = logging.getLogger("sbcabm.measures.calibration")

_ASC_EXPRESSIONS = {"@1", "1"}
_SHARE_FLOOR = 1e-6


def calibrate_asc(
    spec: pd.DataFrame,
    simulate: Callable[[pd.DataFrame], pd.Series],
    targets: dict[str, float],
    *,
    base_alternative: str,
    max_iterations: int = 25,
    damping: float = 0.8,
    tolerance: float = 0.01,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calibrate a spec's ASCs so simulated shares match ``targets``.

    ``simulate`` maps a spec to a Series of simulated shares indexed by
    alternative. ``targets`` maps alternative → target share (should sum to ~1).
    Returns ``(calibrated_spec, history)`` where history records the maximum
    absolute share error per iteration.
    """
    asc_rows = spec.index[spec["expression"].str.strip().isin(_ASC_EXPRESSIONS)]
    if len(asc_rows) != 1:
        raise ValueError("spec must contain exactly one ASC row (expression '@1')")
    asc_row = asc_rows[0]
    if base_alternative not in spec.columns:
        raise ValueError(f"base alternative '{base_alternative}' is not a spec column")

    current = spec.copy()
    history = []
    max_error = float("inf")
    for iteration in range(1, max_iterations + 1):
        shares = simulate(current)
        max_error = max(
            abs(float(shares.get(alt, 0.0)) - target) for alt, target in targets.items()
        )
        history.append({"iteration": iteration, "max_share_error": max_error})
        if max_error < tolerance:
            break
        # Adjust every alternative by the damped log ratio, then re-anchor so
        # the base alternative's ASC stays fixed (subtract its adjustment).
        adjustments = {
            alt: damping
            * math.log(
                max(target, _SHARE_FLOOR) / max(float(shares.get(alt, 0.0)), _SHARE_FLOOR)
            )
            for alt, target in targets.items()
        }
        anchor = adjustments.get(base_alternative, 0.0)
        for alt, adjustment in adjustments.items():
            if alt == base_alternative:
                continue
            current.loc[asc_row, alt] = (
                float(current.loc[asc_row, alt]) + adjustment - anchor
            )

    logger.info(
        "ASC calibration finished after %d iterations (max share error %.4f)",
        len(history),
        max_error,
    )
    return current, pd.DataFrame(history)


def save_calibrated_spec(spec: pd.DataFrame, original_path: str | Path) -> Path:
    """Write a calibrated spec next to the original, never overwriting it."""
    original = Path(original_path)
    out = original.with_suffix(".calibrated.csv")
    spec.to_csv(out, index=False)
    logger.info("wrote calibrated spec to %s", out)
    return out
