"""Validation targets and the model-vs-observed gap report (story 7.2).

Targets are a CSV with columns ``measure, segment, observed, source`` — the
same (measure, segment) keys the measures stage produces, an observed value,
and a free-text provenance note. The gap report joins modeled to observed and
quantifies the deviation.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("sbcabm.measures.validation")

TARGET_COLUMNS = ("measure", "segment", "observed", "source")


def load_targets(path: str | Path) -> pd.DataFrame:
    """Load and validate a targets CSV."""
    targets = pd.read_csv(path)
    missing = [c for c in TARGET_COLUMNS if c not in targets.columns]
    if missing:
        raise ValueError(f"targets file {path} is missing columns: {missing}")
    targets["observed"] = pd.to_numeric(targets["observed"], errors="coerce")
    return targets


def gap_report(measures: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """Join modeled measures to observed targets and quantify the gaps.

    Returns one row per target with ``modeled``, ``observed``, ``difference``
    and ``pct_deviation`` (NaN when the observed value is zero). Targets with
    no matching modeled measure get a NaN ``modeled`` so misses are visible.
    """
    report = targets.merge(
        measures.rename(columns={"value": "modeled"}),
        on=["measure", "segment"],
        how="left",
    )
    report["difference"] = report["modeled"] - report["observed"]
    with np.errstate(divide="ignore", invalid="ignore"):
        report["pct_deviation"] = np.where(
            report["observed"] != 0,
            100.0 * report["difference"] / report["observed"],
            np.nan,
        )
    matched = report["modeled"].notna().sum()
    logger.info("gap report: %d/%d targets matched by modeled measures", matched, len(report))
    return report
