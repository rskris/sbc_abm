"""Measures, validation, calibration, and scenario comparison (Epic 7).

Turns a finished model run into the numbers planners consume — VMT, mode
shares, boardings, travel times — and provides the machinery to compare them
against observed targets, calibrate constants toward those targets, and diff
scenarios.
"""

from __future__ import annotations

from .calibration import calibrate_asc, save_calibrated_spec
from .measures import compute_measures
from .scenario import compare_measures
from .validation import gap_report, load_targets

__all__ = [
    "calibrate_asc",
    "compare_measures",
    "compute_measures",
    "gap_report",
    "load_targets",
    "save_calibrated_spec",
]
