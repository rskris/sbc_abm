"""Tests for trip mode choice, stop frequency, and stop purpose."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sbcabm.choice import load_spec
from sbcabm.modechoice.stops import (
    STOP_FREQUENCY_ALTS,
    run_stop_frequency,
    sample_stop_purpose,
)
from sbcabm.modechoice.trip_mode import _CONSISTENT, run_trip_mode_choice
from sbcabm.modechoice.trips import generate_trips

REPO_ROOT = Path(__file__).resolve().parents[1]
SPECS = REPO_ROOT / "configs" / "specs"


def _skims() -> pd.DataFrame:
    rows = []
    times = {"auto": (2.0, 6.0), "walk": (10.0, 40.0), "bike": (5.0, 15.0)}
    for mode in ("auto", "walk", "bike"):
        for o in ("z1", "z2"):
            for d in ("z1", "z2"):
                t = times[mode][0 if o == d else 1]
                rows.append((o, d, mode, t, 1.0))
    return pd.DataFrame(rows, columns=["origin_zone", "dest_zone", "mode", "time_min", "dist_mi"])


def _zones() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "zone_id": ["z1", "z2"],
            "emp_total": [80.0, 40.0],
            "emp_retail": [30.0, 5.0],
            "emp_service": [25.0, 5.0],
        }
    )


# --- Stop frequency ----------------------------------------------------------

def test_stop_frequency_returns_valid_counts():
    tours = pd.DataFrame(
        {"tour_id": range(100), "purpose": ["work"] * 100, "tour_category": ["mandatory"] * 100}
    )
    spec = load_spec(SPECS / "stop_frequency.csv")
    out_stops, in_stops = run_stop_frequency(tours, spec, rng=np.random.default_rng(0))
    assert len(out_stops) == len(in_stops) == 100
    assert set(np.unique(out_stops)).issubset({0, 1, 2})
    assert set(np.unique(in_stops)).issubset({0, 1, 2})


def test_stop_frequency_alts_cover_zero_to_two():
    counts = set(STOP_FREQUENCY_ALTS.values())
    assert (0, 0) in counts and (2, 2) in counts
    assert all(0 <= o <= 2 and 0 <= i <= 2 for o, i in counts)


def test_stop_frequency_empty():
    spec = load_spec(SPECS / "stop_frequency.csv")
    empty = pd.DataFrame(columns=["purpose", "tour_category"])
    out_stops, in_stops = run_stop_frequency(empty, spec, rng=np.random.default_rng(0))
    assert len(out_stops) == 0 and len(in_stops) == 0


# --- Stop purpose ------------------------------------------------------------

def test_sample_stop_purpose_valid_and_distributed():
    rng = np.random.default_rng(0)
    draws = [sample_stop_purpose("work", rng) for _ in range(2000)]
    assert set(draws).issubset({"shopping", "other", "eatout"})
    # 'other' is the modal stop purpose for work tours (0.4 weight).
    counts = pd.Series(draws).value_counts(normalize=True)
    assert counts.idxmax() == "other"


def test_sample_stop_purpose_unknown_tour_purpose():
    rng = np.random.default_rng(0)
    assert sample_stop_purpose("mystery", rng) in {"shopping", "other", "eatout"}


# --- Trip generation with explicit stop counts -------------------------------

def test_generate_trips_respects_stop_counts():
    tours = pd.DataFrame(
        {
            "tour_id": [0],
            "person_id": [1],
            "household_id": [10],
            "home_zone": ["z1"],
            "dest_zone": ["z2"],
            "purpose": ["work"],
            "tour_mode": ["drive_alone"],
            "start_hour": [8.0],
            "end_hour": [18.0],
        }
    )
    auto = _skims().query("mode == 'auto'")
    trips = generate_trips(
        tours, _zones(), auto, rng=np.random.default_rng(0),
        out_stops=np.array([2]), in_stops=np.array([1]),
    )
    # home → s → s → primary → s → home = 5 legs.
    assert len(trips) == 5
    assert list(trips["outbound"]) == [True, True, True, False, False]


# --- Trip mode choice --------------------------------------------------------

def _trips_and_tours(tour_mode: str):
    tours = pd.DataFrame({"tour_id": [0], "tour_mode": [tour_mode]})
    trips = pd.DataFrame(
        {
            "tour_id": [0, 0],
            "person_id": [1, 1],
            "household_id": [10, 10],
            "origin_zone": ["z1", "z2"],
            "dest_zone": ["z2", "z1"],
            "mode": [tour_mode, tour_mode],
        }
    )
    return trips, tours


def test_trip_mode_consistent_with_tour_mode():
    spec = load_spec(SPECS / "tour_mode_choice.csv")
    households = pd.DataFrame({"household_id": [10], "auto_ownership": ["cars_1"]})
    for tour_mode in ("drive_alone", "walk_transit", "walk", "bike"):
        trips, tours = _trips_and_tours(tour_mode)
        modes = run_trip_mode_choice(
            trips, tours, households, _skims(), spec, rng=np.random.default_rng(0)
        )
        allowed = set(_CONSISTENT[tour_mode])
        assert set(modes.unique()).issubset(allowed)


def test_trip_mode_carless_no_drive_alone():
    spec = load_spec(SPECS / "tour_mode_choice.csv")
    households = pd.DataFrame({"household_id": [10], "auto_ownership": ["cars_0"]})
    # Many shared_ride tours; trips may pick drive_alone/shared_ride but a carless
    # household must never drive alone.
    tours = pd.DataFrame({"tour_id": range(50), "tour_mode": ["shared_ride"] * 50})
    trips = pd.DataFrame(
        {
            "tour_id": list(range(50)) * 2,
            "person_id": list(range(50)) * 2,
            "household_id": [10] * 100,
            "origin_zone": ["z1"] * 100,
            "dest_zone": ["z2"] * 100,
            "mode": ["shared_ride"] * 100,
        }
    )
    modes = run_trip_mode_choice(
        trips, tours, households, _skims(), spec, rng=np.random.default_rng(1)
    )
    assert (modes != "drive_alone").all()
