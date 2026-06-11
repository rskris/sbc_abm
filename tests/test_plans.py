"""Tests for story 6.3 — agent plans and Charypar–Nagel scoring."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sbcabm.assignment.plans import (
    BETA_PERF,
    TYPICAL_HOURS,
    build_plans,
    make_time_lookup,
    score_plans,
)
from sbcabm.config import load_config
from sbcabm.pipeline import build_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"


def _trips() -> pd.DataFrame:
    # One person: home → work (8:00), work → home (17:00).
    return pd.DataFrame(
        {
            "trip_id": [0, 1],
            "person_id": [1, 1],
            "origin_zone": ["z1", "z2"],
            "dest_zone": ["z2", "z1"],
            "purpose": ["work", "home"],
            "mode": ["drive_alone", "drive_alone"],
            "depart_hour": [8.0, 17.0],
        }
    )


def _skims(auto_min: float = 12.0) -> pd.DataFrame:
    rows = []
    for o, d in (("z1", "z2"), ("z2", "z1")):
        rows.append((o, d, "auto", "free_flow", auto_min, 3.0))
        rows.append((o, d, "walk", "free_flow", 60.0, 3.0))
    return pd.DataFrame(
        rows, columns=["origin_zone", "dest_zone", "mode", "time_period", "time_min", "dist_mi"]
    )


def test_build_plans_alternates_activities_and_legs():
    plans = build_plans(_trips(), make_time_lookup(_skims()))
    person = plans[plans["person_id"] == 1]
    # home act, leg, work act, leg, home act = 5 elements.
    assert list(person["element"]) == ["activity", "leg", "activity", "leg", "activity"]
    assert person.iloc[0]["purpose"] == "home"
    assert person.iloc[2]["purpose"] == "work"
    # Work activity runs from arrival (8:00 + 12 min) to the next departure.
    assert person.iloc[2]["start_hour"] == pytest.approx(8.2)
    assert person.iloc[2]["end_hour"] == pytest.approx(17.0)
    # Final home activity closes the day at 24:00.
    assert person.iloc[4]["end_hour"] == pytest.approx(24.0)


def test_score_penalizes_longer_travel():
    fast = score_plans(build_plans(_trips(), make_time_lookup(_skims(auto_min=5.0))))
    slow = score_plans(build_plans(_trips(), make_time_lookup(_skims(auto_min=60.0))))
    assert fast.loc[1] > slow.loc[1]


def test_score_rewards_typical_duration():
    # A work activity held ~its typical duration scores higher than a tiny one.
    def trips_with_return(return_hour: float) -> pd.DataFrame:
        t = _trips()
        t.loc[1, "depart_hour"] = return_hour
        return t

    lookup = make_time_lookup(_skims())
    typical = score_plans(build_plans(trips_with_return(8.2 + TYPICAL_HOURS["work"]), lookup))
    truncated = score_plans(build_plans(trips_with_return(9.0), lookup))
    assert typical.loc[1] > truncated.loc[1]
    assert BETA_PERF > 0  # scoring direction sanity


def test_time_lookup_prefers_congested_auto():
    congested = pd.DataFrame(
        {
            "origin_zone": ["z1"],
            "dest_zone": ["z2"],
            "mode": ["auto"],
            "time_period": ["congested"],
            "time_min": [30.0],
            "dist_mi": [3.0],
        }
    )
    lookup = make_time_lookup(_skims(auto_min=12.0), congested_auto=congested)
    assert lookup("z1", "z2", "drive_alone") == pytest.approx(30.0)
    assert lookup("z2", "z1", "drive_alone") == pytest.approx(12.0)  # untouched OD


def test_scores_deterministic():
    lookup = make_time_lookup(_skims())
    a = score_plans(build_plans(_trips(), lookup))
    b = score_plans(build_plans(_trips(), lookup))
    pd.testing.assert_series_equal(a, b)


def _offline_pipeline():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config)


def test_plans_stage_runs_offline():
    store = _offline_pipeline().run()
    plans = store.get("plans")
    scores = store.get("plan_scores")
    trips = store.get("trips")

    # Every person with trips has a plan and a score.
    persons_with_trips = set(trips["person_id"].unique())
    assert set(plans["person_id"].unique()) == persons_with_trips
    assert set(scores["person_id"]) == persons_with_trips
    # Plans alternate correctly: first and last elements are activities.
    first_last = plans.groupby("person_id")["element"].agg(["first", "last"])
    assert (first_last["first"] == "activity").all()
    assert (first_last["last"] == "activity").all()


def test_plans_requires_trips():
    with pytest.raises(KeyError, match="plans requires"):
        _offline_pipeline().run(["plans"])
