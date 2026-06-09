"""Tests for auto ownership, work location, and the longterm stage."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sbcabm.choice import load_spec
from sbcabm.config import load_config
from sbcabm.longterm.auto_ownership import AUTO_OWNERSHIP_ALTS, run_auto_ownership
from sbcabm.longterm.work_location import choose_workplace
from sbcabm.pipeline import build_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"
AUTO_SPEC = REPO_ROOT / "configs" / "specs" / "auto_ownership.csv"


def _zones() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "zone_id": ["z1", "z2"],
            "hh_density": [60.0, 17.0],
            "emp_density": [160.0, 33.0],
            "emp_total": [80.0, 40.0],
        }
    )


def test_auto_ownership_assigns_valid_categories():
    households = pd.DataFrame(
        {
            "household_id": range(200),
            "zone_id": ["z1", "z2"] * 100,
            "NP": np.random.default_rng(0).integers(1, 6, 200),
            "HINCP": np.random.default_rng(1).integers(15000, 250000, 200),
        }
    )
    spec = load_spec(AUTO_SPEC)
    choices = run_auto_ownership(households, _zones(), spec, rng=np.random.default_rng(7))
    assert len(choices) == 200
    assert set(choices.unique()).issubset(set(AUTO_OWNERSHIP_ALTS))


def test_auto_ownership_income_raises_ownership():
    # Higher income should shift the distribution toward more cars.
    base = dict(zone_id=["z1"] * 500, NP=[2] * 500)
    spec = load_spec(AUTO_SPEC)
    poor = pd.DataFrame({**base, "household_id": range(500), "HINCP": [20000] * 500})
    rich = pd.DataFrame({**base, "household_id": range(500), "HINCP": [300000] * 500})

    poor_cars = run_auto_ownership(poor, _zones(), spec, rng=np.random.default_rng(2))
    rich_cars = run_auto_ownership(rich, _zones(), spec, rng=np.random.default_rng(2))
    assert (rich_cars == "cars_0").mean() < (poor_cars == "cars_0").mean()


def test_auto_ownership_reproducible():
    households = pd.DataFrame(
        {"household_id": [1, 2], "zone_id": ["z1", "z2"], "NP": [2, 3], "HINCP": [50000, 90000]}
    )
    spec = load_spec(AUTO_SPEC)
    a = run_auto_ownership(households, _zones(), spec, rng=np.random.default_rng(5))
    b = run_auto_ownership(households, _zones(), spec, rng=np.random.default_rng(5))
    pd.testing.assert_series_equal(a, b)


def _auto_skim() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "origin_zone": ["z1", "z1", "z2", "z2"],
            "dest_zone": ["z1", "z2", "z1", "z2"],
            "mode": "auto",
            "time_min": [2.0, 10.0, 10.0, 2.0],
        }
    )


def test_work_location_assigns_zones_with_employment():
    workers = pd.DataFrame({"zone_id": ["z1"] * 100 + ["z2"] * 100})
    choices = choose_workplace(workers, _zones(), _auto_skim(), rng=np.random.default_rng(3))
    assert choices.notna().all()
    assert set(choices.unique()).issubset({"z1", "z2"})


def test_work_location_avoids_zero_employment_zones():
    zones = _zones().copy()
    zones.loc[zones["zone_id"] == "z2", "emp_total"] = 0  # no jobs in z2
    workers = pd.DataFrame({"zone_id": ["z1"] * 50})
    choices = choose_workplace(workers, zones, _auto_skim(), rng=np.random.default_rng(4))
    # With z2 unavailable (no jobs), everyone works in z1.
    assert (choices == "z1").all()


def test_work_location_prefers_closer_jobs():
    # Equal employment in both zones; nearer zone (lower time) should win more.
    zones = _zones().copy()
    zones["emp_total"] = [50.0, 50.0]
    workers = pd.DataFrame({"zone_id": ["z1"] * 400})
    choices = choose_workplace(workers, zones, _auto_skim(), rng=np.random.default_rng(8))
    # z1 is 2 min from z1, z2 is 10 min → the nearer zone draws the majority.
    assert (choices == "z1").mean() > (choices == "z2").mean()


def _offline_pipeline():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config)


def test_longterm_stage_runs_offline():
    store = _offline_pipeline().run(
        ["ingest", "zones", "network", "skims", "popsyn", "longterm"]
    )
    households = store.get("households")
    persons = store.get("persons")

    assert "auto_ownership" in households.columns
    assert set(households["auto_ownership"].unique()).issubset(set(AUTO_OWNERSHIP_ALTS))

    assert "workplace_zone" in persons.columns
    # Working-age persons get a workplace; the assignment is within the zone set.
    assigned = persons["workplace_zone"].dropna()
    assert len(assigned) > 0
    assert set(assigned.unique()).issubset(set(households["zone_id"].unique()))


def test_longterm_requires_upstream_tables():
    pipeline = _offline_pipeline()
    with pytest.raises(KeyError, match="longterm stage requires"):
        pipeline.run(["longterm"])
