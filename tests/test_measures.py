"""Tests for stories 7.1–7.4: measures, validation, calibration, scenarios."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sbcabm.choice import load_spec, mnl_probabilities
from sbcabm.config import load_config
from sbcabm.measures.calibration import calibrate_asc, save_calibrated_spec
from sbcabm.measures.scenario import compare_measures
from sbcabm.measures.validation import gap_report, load_targets
from sbcabm.pipeline import build_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"
TARGETS = REPO_ROOT / "tests" / "fixtures" / "validation" / "targets.csv"


def _offline_store():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config).run()


# --- 7.1 measures --------------------------------------------------------------

def test_measures_internal_consistency():
    store = _offline_store()
    measures = store.get("measures").set_index(["measure", "segment"])
    trips = store.get("trips")

    # Shares sum to 1 within each share measure.
    for share_measure in ("mode_share_trip", "mode_share_tour"):
        total = measures.loc[share_measure]["value"].sum()
        assert total == pytest.approx(1.0)

    # trips_total matches and VMT equals a manual recomputation.
    assert measures.loc[("trips_total", "all"), "value"] == len(trips)
    auto = trips[trips["mode"].isin(("drive_alone", "shared_ride"))]
    dist = store.get("skims").query("mode=='auto'").set_index(
        ["origin_zone", "dest_zone"]
    )["dist_mi"]
    manual_vmt = sum(
        dist.get((t.origin_zone, t.dest_zone), 0.0) for t in auto.itertuples()
    )
    assert measures.loc[("vmt_person_auto", "all"), "value"] == pytest.approx(manual_vmt)
    # Boardings equal transit trips.
    assert measures.loc[("transit_boardings", "all"), "value"] == (
        trips["mode"] == "walk_transit"
    ).sum()


def test_measures_requires_upstream():
    config = load_config(CONFIG)
    with pytest.raises(KeyError, match="measures requires"):
        build_pipeline(config).run(["measures"])


# --- 7.2 validation ------------------------------------------------------------

def test_load_targets_validates_columns(tmp_path):
    bad = tmp_path / "targets.csv"
    bad.write_text("measure,observed\nx,1\n")
    with pytest.raises(ValueError, match="missing columns"):
        load_targets(bad)


def test_gap_report_math_and_unmatched_targets():
    measures = pd.DataFrame(
        {
            "measure": ["mode_share_trip", "trips_per_person"],
            "segment": ["drive_alone", "all"],
            "value": [0.40, 4.4],
        }
    )
    report = gap_report(measures, load_targets(TARGETS)).set_index(["measure", "segment"])

    row = report.loc[("mode_share_trip", "drive_alone")]
    assert row["modeled"] == pytest.approx(0.40)
    assert row["difference"] == pytest.approx(0.05)
    assert row["pct_deviation"] == pytest.approx(100 * 0.05 / 0.35)
    # A target with no modeled counterpart is visible, not dropped.
    assert pd.isna(report.loc[("nonexistent_measure", "all"), "modeled"])


def test_gap_report_from_full_run():
    store = _offline_store()
    report = gap_report(store.get("measures"), load_targets(TARGETS))
    matched = report["modeled"].notna()
    assert matched.sum() == 4  # all but the deliberately unmatched target


# --- 7.3 calibration -----------------------------------------------------------

def _share_simulator(choosers: pd.DataFrame):
    """Aggregate-share simulator for a spec via expected MNL probabilities."""
    from sbcabm.choice import evaluate_utilities

    def simulate(spec: pd.DataFrame) -> pd.Series:
        probs = mnl_probabilities(evaluate_utilities(choosers, spec))
        return probs.mean(axis=0)

    return simulate


def test_calibrate_asc_converges_to_targets(tmp_path):
    spec = load_spec(REPO_ROOT / "configs" / "specs" / "auto_ownership.csv")
    rng = np.random.default_rng(0)
    choosers = pd.DataFrame(
        {
            "NP": rng.integers(1, 5, 500),
            "HINCP": rng.integers(20000, 200000, 500),
            "hh_density": rng.uniform(5, 60, 500),
            "emp_density": rng.uniform(5, 160, 500),
        }
    )
    targets = {"cars_0": 0.10, "cars_1": 0.40, "cars_2": 0.35, "cars_3p": 0.15}
    calibrated, history = calibrate_asc(
        spec, _share_simulator(choosers), targets, base_alternative="cars_0"
    )
    assert history["max_share_error"].iloc[-1] < 0.01
    # Error shrank from start to finish.
    assert history["max_share_error"].iloc[-1] < history["max_share_error"].iloc[0]

    # The calibrated spec is written alongside; the original is untouched.
    original = tmp_path / "auto_ownership.csv"
    spec.to_csv(original, index=False)
    out = save_calibrated_spec(calibrated, original)
    assert out.name == "auto_ownership.calibrated.csv"
    pd.testing.assert_frame_equal(pd.read_csv(original), spec, check_dtype=False)


def test_calibrate_asc_requires_single_asc_row():
    spec = pd.DataFrame({"expression": ["NP"], "a": [0.1], "b": [0.2]})
    with pytest.raises(ValueError, match="exactly one ASC row"):
        calibrate_asc(spec, lambda s: pd.Series(), {"a": 0.5}, base_alternative="a")


# --- 7.4 scenarios ---------------------------------------------------------------

def test_compare_measures_deltas():
    base = pd.DataFrame(
        {"measure": ["vmt", "share"], "segment": ["all", "auto"], "value": [100.0, 0.5]}
    )
    scenario = pd.DataFrame(
        {"measure": ["vmt", "share"], "segment": ["all", "auto"], "value": [90.0, 0.45]}
    )
    cmp = compare_measures(base, scenario).set_index(["measure", "segment"])
    assert cmp.loc[("vmt", "all"), "delta"] == pytest.approx(-10.0)
    assert cmp.loc[("vmt", "all"), "pct_delta"] == pytest.approx(-10.0)


def test_identical_runs_have_zero_deltas():
    a = _offline_store().get("measures")
    b = _offline_store().get("measures")
    cmp = compare_measures(a, b)
    assert np.allclose(cmp["delta"].fillna(0.0), 0.0)
