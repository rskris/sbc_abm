"""Tests for OD1: ACS-built validation targets and the new comparison measures."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sbcabm.config import load_config
from sbcabm.measures.measures import compute_measures
from sbcabm.measures.targets import (
    VALIDATION_ACS_VARIABLES,
    build_acs_targets,
)
from sbcabm.pipeline import build_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"
NHTS = REPO_ROOT / "configs" / "validation" / "nhts2017_targets.csv"


def _acs_row() -> pd.DataFrame:
    return pd.read_csv(
        REPO_ROOT / "tests" / "fixtures" / "census" / "acs_validation.csv"
    )


def test_build_acs_targets_shares_sum_to_one():
    targets = build_acs_targets(_acs_row())
    for measure in ("mode_share_commute", "auto_ownership_share"):
        share_sum = targets.loc[targets["measure"] == measure, "observed"].sum()
        assert share_sum == pytest.approx(1.0)
    # 3 and 4+ vehicle households are folded into cars_3p.
    cars_3p = targets.query("measure=='auto_ownership_share' and segment=='cars_3p'")
    assert cars_3p["observed"].iloc[0] == pytest.approx(32000 / 149000)


def test_build_acs_targets_empty_input():
    targets = build_acs_targets(pd.DataFrame({"NAME": ["x"]}))
    assert targets.empty


def test_validation_variables_are_estimates():
    assert all(v.endswith("E") for v in VALIDATION_ACS_VARIABLES)
    assert "B08301_003E" in VALIDATION_ACS_VARIABLES  # drove alone
    assert "B08201_002E" in VALIDATION_ACS_VARIABLES  # zero-vehicle households


def test_new_measures_commute_share_and_auto_ownership():
    trips = pd.DataFrame(
        {
            "purpose": ["work", "work", "shopping"],
            "mode": ["drive_alone", "walk", "walk"],
            "origin_zone": ["z1"] * 3,
            "dest_zone": ["z1"] * 3,
        }
    )
    households = pd.DataFrame({"auto_ownership": ["cars_0", "cars_1", "cars_1", "cars_2"]})
    skims = pd.DataFrame(
        {
            "origin_zone": ["z1"],
            "dest_zone": ["z1"],
            "mode": ["auto"],
            "time_min": [1.0],
            "dist_mi": [0.5],
        }
    )
    measures = compute_measures(
        persons=pd.DataFrame({"person_id": [1]}),
        tours=pd.DataFrame(),
        trips=trips,
        skims=skims,
        households=households,
    ).set_index(["measure", "segment"])

    # Commute share counts only work-purpose trips (1 DA + 1 walk).
    assert measures.loc[("mode_share_commute", "drive_alone"), "value"] == pytest.approx(0.5)
    assert measures.loc[("mode_share_commute", "walk"), "value"] == pytest.approx(0.5)
    # Auto-ownership shares from households.
    assert measures.loc[("auto_ownership_share", "cars_1"), "value"] == pytest.approx(0.5)


def test_pipeline_gap_report_merges_acs_and_file_targets():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    store = build_pipeline(config).run()

    gaps = store.get("validation_gaps")
    sources = set(gaps["source"].unique())
    # Both target families present: auto-built ACS + curated NHTS file.
    assert any("B08301" in s for s in sources)
    assert any("NHTS" in s for s in sources)
    # Every target matched a modeled measure (no NaN modeled values).
    assert gaps["modeled"].notna().all()
    # And the comparable measures exist on the modeled side.
    measures = set(store.get("measures")["measure"].unique())
    assert {"mode_share_commute", "auto_ownership_share"}.issubset(measures)


def test_nhts_targets_file_is_valid():
    from sbcabm.measures.validation import load_targets

    targets = load_targets(NHTS)
    assert (targets["observed"] > 0).all()
    shares = targets[targets["measure"] == "mode_share_trip"]["observed"].sum()
    assert shares == pytest.approx(0.96, abs=0.05)  # major modes; remainder is other
