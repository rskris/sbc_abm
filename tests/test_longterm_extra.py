"""Tests for the remaining Phase 3 models: school location, transit pass,
telecommute, and destination-choice alternative sampling."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sbcabm.choice import load_spec
from sbcabm.choice.destination import destination_choice
from sbcabm.config import load_config
from sbcabm.longterm.mobility import run_telecommute, run_transit_pass
from sbcabm.longterm.school_location import choose_school
from sbcabm.pipeline import build_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"
SPECS = REPO_ROOT / "configs" / "specs"


def _zones(n: int = 2) -> pd.DataFrame:
    if n == 2:
        return pd.DataFrame(
            {
                "zone_id": ["z1", "z2"],
                "emp_total": [80.0, 40.0],
                "emp_education": [0.0, 10.0],
            }
        )
    rng = np.random.default_rng(0)
    ids = [f"z{i}" for i in range(n)]
    return pd.DataFrame({"zone_id": ids, "emp_total": rng.integers(10, 200, n).astype(float)})


def _auto_skim(zone_ids) -> pd.DataFrame:
    rows = []
    for o in zone_ids:
        for d in zone_ids:
            rows.append((o, d, "auto", 2.0 if o == d else 12.0))
    return pd.DataFrame(rows, columns=["origin_zone", "dest_zone", "mode", "time_min"])


# --- School location ---------------------------------------------------------

def test_school_location_uses_education_size():
    # emp_education is only positive in z2 → all students go to z2.
    students = pd.DataFrame({"zone_id": ["z1"] * 50})
    skim = _auto_skim(["z1", "z2"])
    choices = choose_school(students, _zones(), skim, rng=np.random.default_rng(0))
    assert (choices == "z2").all()


def test_school_location_falls_back_to_total_employment():
    zones = _zones().copy()
    zones["emp_education"] = 0.0  # no education employment anywhere
    students = pd.DataFrame({"zone_id": ["z1"] * 50})
    choices = choose_school(students, zones, _auto_skim(["z1", "z2"]), rng=np.random.default_rng(0))
    # Falls back to emp_total; both zones now feasible.
    assert set(choices.unique()).issubset({"z1", "z2"})


# --- Transit pass ------------------------------------------------------------

def test_transit_pass_higher_for_carless():
    spec = load_spec(SPECS / "transit_pass.csv")
    carless = pd.DataFrame({"AGEP": [30] * 400, "auto_ownership": ["cars_0"] * 400})
    carful = pd.DataFrame({"AGEP": [30] * 400, "auto_ownership": ["cars_2"] * 400})
    p_carless = run_transit_pass(carless, spec, rng=np.random.default_rng(1)).mean()
    p_carful = run_transit_pass(carful, spec, rng=np.random.default_rng(1)).mean()
    assert p_carless > p_carful
    assert run_transit_pass(carless, spec, rng=np.random.default_rng(1)).dtype == bool


# --- Telecommute -------------------------------------------------------------

def test_telecommute_levels_and_income_gradient():
    spec = load_spec(SPECS / "telecommute.csv")
    poor = pd.DataFrame({"AGEP": [40] * 400, "HINCP": [20000] * 400})
    rich = pd.DataFrame({"AGEP": [40] * 400, "HINCP": [300000] * 400})
    poor_tc = run_telecommute(poor, spec, rng=np.random.default_rng(2))
    rich_tc = run_telecommute(rich, spec, rng=np.random.default_rng(2))
    # Higher income → less likely to never telecommute.
    assert (rich_tc == "tc_none").mean() < (poor_tc == "tc_none").mean()


def test_telecommute_empty_workers():
    spec = load_spec(SPECS / "telecommute.csv")
    assert run_telecommute(pd.DataFrame(), spec, rng=np.random.default_rng(0)).empty


# --- Alternative sampling ----------------------------------------------------

def test_destination_sampling_returns_valid_choices():
    zones = _zones(40)
    zone_ids = zones["zone_id"].tolist()
    choosers = pd.DataFrame({"zone_id": ["z0"] * 200})
    choices = destination_choice(
        choosers, zones, _auto_skim(zone_ids), rng=np.random.default_rng(3),
        size_col="emp_total", sample_size=8,
    )
    assert choices.notna().all()
    assert set(choices.unique()).issubset(set(zone_ids))


def test_sampling_approximates_full_enumeration():
    # With many draws, uniform alternative sampling matches full enumeration in
    # aggregate (no correction needed because inclusion is uniform).
    zones = _zones(20)
    zone_ids = zones["zone_id"].tolist()
    skim = _auto_skim(zone_ids)
    choosers = pd.DataFrame({"zone_id": ["z0"] * 6000})

    full = destination_choice(
        choosers, zones, skim, rng=np.random.default_rng(4), size_col="emp_total"
    )
    sampled = destination_choice(
        choosers, zones, skim, rng=np.random.default_rng(4), size_col="emp_total", sample_size=10
    )
    full_share = full.value_counts(normalize=True)
    sampled_share = sampled.value_counts(normalize=True).reindex(full_share.index).fillna(0)
    # Mean absolute difference in zone shares is small.
    assert (full_share - sampled_share).abs().mean() < 0.03


# --- Stage integration -------------------------------------------------------

def _offline_pipeline():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config)


def test_longterm_stage_produces_all_choices():
    store = _offline_pipeline().run(["ingest", "zones", "network", "skims", "popsyn", "longterm"])
    persons = store.get("persons")
    for col in ("workplace_zone", "school_zone", "transit_pass", "telecommute_freq"):
        assert col in persons.columns

    # Students get schools, workers get telecommute frequencies.
    assert persons["school_zone"].notna().sum() > 0
    assert persons["transit_pass"].dtype == bool
    workers = persons["workplace_zone"].notna()
    assert persons.loc[workers, "telecommute_freq"].notna().all()


def test_school_tours_route_to_school_zone():
    store = _offline_pipeline().run(
        ["ingest", "zones", "network", "skims", "popsyn", "longterm", "activitygen"]
    )
    persons = store.get("persons").set_index("person_id")
    tours = store.get("tours")
    school = tours[tours["purpose"] == "school"]
    assert len(school) > 0
    for row in school.itertuples():
        expected = persons.loc[row.person_id, "school_zone"]
        if pd.notna(expected):
            assert row.dest_zone == expected
