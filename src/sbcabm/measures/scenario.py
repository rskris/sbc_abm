"""Scenario comparison (story 7.4).

Run the pipeline under two configurations (base vs. scenario) and diff their
measures. Deterministic seeds make the comparison itself deterministic.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("sbcabm.measures.scenario")


def compare_measures(base: pd.DataFrame, scenario: pd.DataFrame) -> pd.DataFrame:
    """Outer-join two measures tables and compute absolute/percent deltas."""
    merged = base.rename(columns={"value": "base"}).merge(
        scenario.rename(columns={"value": "scenario"}),
        on=["measure", "segment"],
        how="outer",
    )
    merged["delta"] = merged["scenario"] - merged["base"]
    with np.errstate(divide="ignore", invalid="ignore"):
        merged["pct_delta"] = np.where(
            merged["base"] != 0, 100.0 * merged["delta"] / merged["base"], np.nan
        )
    return merged


def run_and_compare(
    base_config_path: str | Path,
    scenario_config_path: str | Path,
    *,
    stages: list[str] | None = None,
) -> pd.DataFrame:
    """Run both configs end-to-end and return the measure comparison."""
    from ..config import load_config
    from ..pipeline import build_pipeline

    frames = []
    for path in (base_config_path, scenario_config_path):
        pipeline = build_pipeline(load_config(path))
        store = pipeline.run(stages)
        if not store.has("measures"):
            raise KeyError(f"run of {path} produced no 'measures' table")
        frames.append(store.get("measures"))
    comparison = compare_measures(frames[0], frames[1])
    logger.info("compared %d measures across base/scenario", len(comparison))
    return comparison
