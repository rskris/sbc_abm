"""Tests for the remaining Phase 4 modules: household-interaction CDAP,
joint tours, and discrete time-of-day choice."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sbcabm.activitygen.cdap import CDAP_PATTERNS, run_cdap, run_cdap_household
from sbcabm.activitygen.joint_tours import generate_joint_tours
from sbcabm.activitygen.scheduling import choose_time_of_day, period_of
from sbcabm.choice import load_spec
from sbcabm.config import load_config
from sbcabm.pipeline import build_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"
CDAP_SPEC = REPO_ROOT / "configs" / "specs" / "cdap.csv"


# --- Household-interaction CDAP ---------------------------------------------

def test_household_cdap_assigns_all_members():
    persons = pd.DataFrame(
        {
            "person_id": [1, 2, 3, 4],
            "household_id": [10, 10, 20, 20],
            "AGEP": [40, 38, 70, 68],
            "workplace_zone": ["z1", "z1", None, None],
        }
    )
    spec = load_spec(CDAP_SPEC)
    choices = run_cdap_household(persons, spec, rng=np.random.default_rng(0))
    assert len(choices) == 4
    assert set(choices.unique()).issubset(set(CDAP_PATTERNS))


def test_interaction_increases_household_coordination():
    # Two seniors in one household; the home-home interaction should make both
    # being home more likely than under independent person-level CDAP.
    persons = pd.DataFrame(
        {
            "person_id": [1, 2],
            "household_id": [99, 99],
            "AGEP": [72, 70],
            "workplace_zone": [None, None],
        }
    )
    spec = load_spec(CDAP_SPEC)

    def share_both_home(fn):
        both = 0
        trials = 120
        for seed in range(trials):
            choices = fn(persons, spec, rng=np.random.default_rng(seed))
            both += int((choices == "home").all())
        return both / trials

    joint = share_both_home(run_cdap_household)
    independent = share_both_home(run_cdap)
    assert joint > independent


def test_strong_home_interaction_dominates():
    persons = pd.DataFrame(
        {
            "person_id": [1, 2],
            "household_id": [1, 1],
            "AGEP": [40, 40],
            "workplace_zone": [None, None],
        }
    )
    spec = load_spec(CDAP_SPEC)
    strong = {frozenset({"home"}): 8.0}  # overwhelming pull to home
    choices = run_cdap_household(persons, spec, rng=np.random.default_rng(0), interaction=strong)
    assert (choices == "home").all()


# --- Joint tours -------------------------------------------------------------

def _zones() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "zone_id": ["z1", "z2"],
            "emp_total": [80.0, 40.0],
            "emp_retail": [30.0, 5.0],
            "emp_service": [25.0, 5.0],
        }
    )


def _auto_skim() -> pd.DataFrame:
    rows = [(o, d, "auto", 2.0 if o == d else 10.0) for o in ("z1", "z2") for d in ("z1", "z2")]
    return pd.DataFrame(rows, columns=["origin_zone", "dest_zone", "mode", "time_min"])


def test_joint_tours_share_id_and_destination():
    # A 3-person household all leaving home → eligible for a joint tour.
    persons = pd.DataFrame(
        {
            "person_id": [1, 2, 3],
            "household_id": [5, 5, 5],
            "zone_id": ["z1", "z1", "z1"],
            "daily_pattern": ["nonmandatory", "nonmandatory", "mandatory"],
        }
    )
    joint = generate_joint_tours(
        persons, _zones(), _auto_skim(), rng=np.random.default_rng(0), joint_probability=1.0
    )
    assert (joint["tour_category"] == "joint").all()
    assert joint["joint_tour_id"].nunique() == 1  # one joint tour
    assert len(joint) == 3  # all three members participate
    # All participants share one destination.
    assert joint["dest_zone"].nunique() == 1


def test_no_joint_tour_for_single_traveler_household():
    persons = pd.DataFrame(
        {
            "person_id": [1, 2],
            "household_id": [7, 7],
            "zone_id": ["z1", "z1"],
            "daily_pattern": ["nonmandatory", "home"],  # only one leaves home
        }
    )
    joint = generate_joint_tours(
        persons, _zones(), _auto_skim(), rng=np.random.default_rng(0), joint_probability=1.0
    )
    assert joint.empty


# --- Discrete time-of-day ----------------------------------------------------

def test_time_of_day_orders_purposes():
    tours = pd.DataFrame(
        {"tour_id": range(200), "purpose": ["work"] * 100 + ["shopping"] * 100}
    )
    scheduled = choose_time_of_day(tours, rng=np.random.default_rng(0))
    assert (scheduled["end_hour"] > scheduled["start_hour"]).all()
    work = scheduled[scheduled["purpose"] == "work"]
    shop = scheduled[scheduled["purpose"] == "shopping"]
    # Work tours start earlier and last longer than shopping tours.
    assert work["start_hour"].mean() < shop["start_hour"].mean()
    assert (work["end_hour"] - work["start_hour"]).mean() > (
        shop["end_hour"] - shop["start_hour"]
    ).mean()


def test_time_of_day_assigns_valid_periods():
    tours = pd.DataFrame({"tour_id": [0, 1], "purpose": ["work", "other"]})
    scheduled = choose_time_of_day(tours, rng=np.random.default_rng(1))
    assert set(scheduled["period"]).issubset({"EA", "AM", "MD", "PM", "EV"})
    pairs = zip(scheduled["start_hour"], scheduled["period"], strict=True)
    assert all(period_of(h) == p for h, p in pairs)


def test_time_of_day_reproducible():
    tours = pd.DataFrame({"tour_id": range(20), "purpose": ["work"] * 20})
    a = choose_time_of_day(tours, rng=np.random.default_rng(3))
    b = choose_time_of_day(tours, rng=np.random.default_rng(3))
    pd.testing.assert_frame_equal(a, b)


# --- Stage integration -------------------------------------------------------

def _offline_pipeline():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config)


def test_activitygen_produces_joint_tours_and_tod():
    store = _offline_pipeline().run(
        ["ingest", "zones", "network", "skims", "popsyn", "longterm", "activitygen"]
    )
    tours = store.get("tours")
    assert "joint_tour_id" in tours.columns
    assert "tour_category" in tours.columns
    assert set(tours["tour_category"].unique()).issubset({"mandatory", "nonmandatory", "joint"})

    # Joint tours (if any) share a destination within each joint group.
    joint = tours[tours["tour_category"] == "joint"]
    if not joint.empty:
        per_group = joint.groupby("joint_tour_id")["dest_zone"].nunique()
        assert (per_group == 1).all()

    # Every tour got a discrete time-of-day window.
    assert tours["start_hour"].notna().all()
    assert (tours["end_hour"] > tours["start_hour"]).all()
