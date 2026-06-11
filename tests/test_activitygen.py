"""Tests for daily activity pattern, tour generation, and scheduling."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sbcabm.activitygen.cdap import CDAP_PATTERNS, run_cdap
from sbcabm.activitygen.scheduling import period_of, schedule_tours
from sbcabm.activitygen.tours import (
    assign_destinations,
    generate_tours,
    run_nonmandatory_frequency,
)
from sbcabm.choice import load_spec
from sbcabm.config import load_config
from sbcabm.pipeline import build_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"
SPECS = REPO_ROOT / "configs" / "specs"


def _zones() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "zone_id": ["z1", "z2"],
            "emp_total": [80.0, 40.0],
            "emp_retail": [30.0, 5.0],
            "emp_service": [25.0, 5.0],
            "emp_education": [0.0, 10.0],
        }
    )


def _auto_skim() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "origin_zone": ["z1", "z1", "z2", "z2"],
            "dest_zone": ["z1", "z2", "z1", "z2"],
            "mode": "auto",
            "time_min": [2.0, 10.0, 10.0, 2.0],
        }
    )


def test_cdap_assigns_patterns_by_role():
    # A worker, a school-age child, a toddler, a senior.
    persons = pd.DataFrame(
        {
            "person_id": [1, 2, 3, 4],
            "AGEP": [40, 10, 2, 80],
            "workplace_zone": ["z1", None, None, None],
        }
    )
    spec = load_spec(SPECS / "cdap.csv")
    # Run many times to read the modal pattern per person robustly.
    counts = {i: {p: 0 for p in CDAP_PATTERNS} for i in persons.index}
    for seed in range(40):
        choices = run_cdap(persons, spec, rng=np.random.default_rng(seed))
        for i, pat in choices.items():
            counts[i][pat] += 1
    modal = {i: max(counts[i], key=counts[i].get) for i in persons.index}
    assert modal[0] == "mandatory"  # worker
    assert modal[1] == "mandatory"  # school-age child
    assert modal[2] == "home"  # toddler
    assert set(CDAP_PATTERNS) >= {modal[3]}  # senior: nonmandatory/home


def test_nonmandatory_frequency_forces_tour_for_nonmandatory_pattern():
    persons = pd.DataFrame(
        {
            "person_id": [1, 2, 3],
            "daily_pattern": ["home", "nonmandatory", "mandatory"],
            "auto_ownership": ["cars_1", "cars_1", "cars_0"],
            "AGEP": [30, 40, 50],
        }
    )
    spec = load_spec(SPECS / "nonmandatory_tour_frequency.csv")
    counts = run_nonmandatory_frequency(persons, spec, rng=np.random.default_rng(0))
    assert counts.loc[0] == 0  # home → no tours
    assert counts.loc[1] >= 1  # nonmandatory pattern → at least one


def test_generate_tours_creates_mandatory_and_nonmandatory():
    persons = pd.DataFrame(
        {
            "person_id": [1, 2],
            "household_id": [10, 10],
            "zone_id": ["z1", "z1"],
            "daily_pattern": ["mandatory", "nonmandatory"],
            "workplace_zone": ["z2", None],
        }
    )
    nm_counts = pd.Series([1, 2], index=persons.index)
    tours = generate_tours(persons, nm_counts, rng=np.random.default_rng(0))
    # Person 1: 1 work tour + 1 nonmandatory; person 2: 2 nonmandatory.
    assert len(tours) == 4
    assert (tours["purpose"] == "work").sum() == 1
    assert tours["tour_id"].is_unique
    assert set(tours["tour_category"]) == {"mandatory", "nonmandatory"}


def test_assign_destinations_work_goes_to_workplace():
    persons = pd.DataFrame(
        {"person_id": [1], "workplace_zone": ["z2"]}
    )
    tours = pd.DataFrame(
        {
            "tour_id": [0, 1],
            "person_id": [1, 1],
            "household_id": [10, 10],
            "tour_category": ["mandatory", "nonmandatory"],
            "purpose": ["work", "shopping"],
            "home_zone": ["z1", "z1"],
        }
    )
    out = assign_destinations(
        tours, persons, _zones(), _auto_skim(), rng=np.random.default_rng(0)
    )
    assert out.loc[out["purpose"] == "work", "dest_zone"].iloc[0] == "z2"
    # Shopping destination is one of the zones.
    assert out.loc[out["purpose"] == "shopping", "dest_zone"].iloc[0] in {"z1", "z2"}


def test_schedule_tours_orders_and_periods():
    tours = pd.DataFrame(
        {
            "tour_id": range(50),
            "purpose": ["work"] * 25 + ["shopping"] * 25,
        }
    )
    scheduled = schedule_tours(tours, rng=np.random.default_rng(0))
    assert (scheduled["end_hour"] > scheduled["start_hour"]).all()
    work = scheduled[scheduled["purpose"] == "work"]["start_hour"]
    shop = scheduled[scheduled["purpose"] == "shopping"]["start_hour"]
    # Work tours start earlier than shopping tours on average.
    assert work.mean() < shop.mean()


def test_period_of_boundaries():
    assert period_of(7.0) == "AM"
    assert period_of(12.0) == "MD"
    assert period_of(16.0) == "PM"
    assert period_of(20.0) == "EV"


def _offline_pipeline():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config)


def test_activitygen_stage_runs_offline():
    store = _offline_pipeline().run(
        ["ingest", "zones", "network", "skims", "popsyn", "longterm", "activitygen"]
    )
    persons = store.get("persons")
    tours = store.get("tours")

    assert "daily_pattern" in persons.columns
    assert set(persons["daily_pattern"].unique()).issubset(set(CDAP_PATTERNS))

    assert len(tours) > 0
    assert {"purpose", "dest_zone", "start_hour", "end_hour", "period"}.issubset(tours.columns)
    # Every tour has a valid destination and a sensible time window.
    assert tours["dest_zone"].notna().all()
    assert (tours["end_hour"] > tours["start_hour"]).all()
    # Mandatory tours only come from mandatory-pattern persons.
    mandatory_persons = set(persons.loc[persons["daily_pattern"] == "mandatory", "person_id"])
    assert set(tours.loc[tours["tour_category"] == "mandatory", "person_id"]).issubset(
        mandatory_persons
    )


def test_activitygen_requires_upstream():
    with pytest.raises(KeyError, match="activitygen requires"):
        _offline_pipeline().run(["activitygen"])
