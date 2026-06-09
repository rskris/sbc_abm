"""Tests for tour mode choice (nested logit), LOS, and trip generation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sbcabm.choice import load_spec
from sbcabm.config import load_config
from sbcabm.modechoice.los import build_mode_los
from sbcabm.modechoice.tour_mode import TOUR_MODES, run_tour_mode_choice
from sbcabm.modechoice.trips import generate_trips
from sbcabm.pipeline import build_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"
MODE_SPEC = REPO_ROOT / "configs" / "specs" / "tour_mode_choice.csv"


def _skims() -> pd.DataFrame:
    rows = []
    times = {"auto": (2.0, 6.0), "walk": (10.0, 40.0), "bike": (5.0, 15.0)}
    dist = {"auto": (0.5, 3.0), "walk": (0.5, 3.0), "bike": (0.5, 3.0)}
    for mode in ("auto", "walk", "bike"):
        for o in ("z1", "z2"):
            for d in ("z1", "z2"):
                i = 0 if o == d else 1
                rows.append((o, d, mode, times[mode][i], dist[mode][i]))
    return pd.DataFrame(rows, columns=["origin_zone", "dest_zone", "mode", "time_min", "dist_mi"])


def _transit_skims() -> pd.DataFrame:
    return pd.DataFrame(
        {"origin_zone": ["z1"], "dest_zone": ["z2"], "total_time_min": [15.0]}
    )


def _tours(home="z1", dest="z2", n=1) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "tour_id": range(n),
            "person_id": range(n),
            "household_id": [100] * n,
            "home_zone": [home] * n,
            "dest_zone": [dest] * n,
            "purpose": ["work"] * n,
            "start_hour": [8.0] * n,
            "end_hour": [17.0] * n,
        }
    )


def _households(auto="cars_1") -> pd.DataFrame:
    return pd.DataFrame({"household_id": [100], "auto_ownership": [auto]})


def _zones() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "zone_id": ["z1", "z2"],
            "emp_total": [80.0, 40.0],
            "emp_retail": [30.0, 5.0],
            "emp_service": [25.0, 5.0],
        }
    )


def test_build_mode_los_looks_up_skims():
    los = build_mode_los(_tours(), _skims(), _transit_skims())
    assert los.loc[0, "auto_time"] == 6.0
    assert los.loc[0, "walk_time"] == 40.0
    assert los.loc[0, "transit_time"] == 15.0
    assert los.loc[0, "auto_cost"] == pytest.approx(3.0 * 0.20)
    assert los.loc[0, "transit_cost"] == 1.75


def test_transit_unavailable_when_no_skim():
    # z2→z1 has no transit skim in the fixture → transit_time NaN.
    los = build_mode_los(_tours(home="z2", dest="z1"), _skims(), _transit_skims())
    assert pd.isna(los.loc[0, "transit_time"])
    assert pd.isna(los.loc[0, "transit_cost"])


def test_tour_mode_choice_returns_valid_modes():
    spec = load_spec(MODE_SPEC)
    tours = _tours(n=200)
    modes = run_tour_mode_choice(
        tours, _households(), _skims(), spec, transit_skims=_transit_skims(),
        rng=np.random.default_rng(0),
    )
    assert len(modes) == 200
    assert set(modes.unique()).issubset(set(TOUR_MODES))


def test_carless_household_never_drives_alone():
    spec = load_spec(MODE_SPEC)
    tours = _tours(n=300)
    modes = run_tour_mode_choice(
        tours, _households(auto="cars_0"), _skims(), spec,
        transit_skims=_transit_skims(), rng=np.random.default_rng(1),
    )
    assert (modes != "drive_alone").all()
    # Shared ride remains available as a passenger.
    assert "shared_ride" in set(modes.unique())


def test_generate_trips_basic_tour_has_two_legs():
    tours = _tours(n=1)
    tours["tour_mode"] = "drive_alone"
    # No stops: force stop_probability 0.
    auto = _skims().query("mode=='auto'")
    trips = generate_trips(tours, _zones(), auto, rng=np.random.default_rng(0), stop_probability=0.0)
    assert len(trips) == 2
    assert list(trips["outbound"]) == [True, False]
    assert (trips["mode"] == "drive_alone").all()
    # First trip leaves home, last returns home.
    assert trips.iloc[0]["origin_zone"] == "z1"
    assert trips.iloc[-1]["dest_zone"] == "z1"
    assert (trips["depart_hour"] >= 8.0).all() and (trips["depart_hour"] <= 17.0).all()


def test_generate_trips_with_stops_adds_legs():
    tours = _tours(n=1)
    tours["tour_mode"] = "shared_ride"
    trips = generate_trips(
        tours, _zones(), _skims().query("mode=='auto'"), rng=np.random.default_rng(0),
        stop_probability=1.0,  # force a stop each direction
    )
    # home → stop → primary → stop → home = 4 legs.
    assert len(trips) == 4
    assert (trips["mode"] == "shared_ride").all()


def _offline_pipeline():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config)


def test_modechoice_stage_runs_offline():
    store = _offline_pipeline().run()
    tours = store.get("tours")
    trips = store.get("trips")

    assert "tour_mode" in tours.columns
    assert set(tours["tour_mode"].unique()).issubset(set(TOUR_MODES))

    assert len(trips) >= len(tours)  # at least two legs per tour
    assert {"origin_zone", "dest_zone", "mode", "depart_hour"}.issubset(trips.columns)
    # Every trip's mode is its tour's mode.
    tour_mode = tours.set_index("tour_id")["tour_mode"]
    assert (trips["mode"] == trips["tour_id"].map(tour_mode)).all()


def test_modechoice_requires_tours():
    with pytest.raises(KeyError, match="modechoice requires"):
        _offline_pipeline().run(["modechoice"])
