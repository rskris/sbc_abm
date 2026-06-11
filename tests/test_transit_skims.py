"""Tests for schedule-based transit routing (RAPTOR) and transit skims."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sbcabm.config import load_config
from sbcabm.data.transit import load_gtfs
from sbcabm.pipeline import build_pipeline
from sbcabm.skims.transit import (
    Pattern,
    build_timetable,
    compute_transit_skims,
    haversine_mi,
    parse_gtfs_time,
    raptor,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"
GTFS_DIR = REPO_ROOT / "tests" / "fixtures" / "gtfs"

# The two block-group centroids coincide with the two fixture stops.
ZONES = pd.DataFrame(
    {
        "zone_id": ["060830001001", "060830001002"],
        "centroid_x": [-119.70, -119.72],  # lon
        "centroid_y": [34.42, 34.43],  # lat
    }
)


def test_parse_gtfs_time_handles_after_midnight():
    assert parse_gtfs_time("08:00:00") == 8 * 3600
    assert parse_gtfs_time("25:30:00") == 25 * 3600 + 30 * 60


def test_haversine_known_distance():
    # ~0.69 mi per 0.01 degree of latitude.
    d = haversine_mi(34.42, -119.70, 34.43, -119.70)
    assert d == pytest.approx(0.69, abs=0.02)


def test_build_timetable_groups_trips_into_patterns():
    tt = build_timetable(load_gtfs(GTFS_DIR))
    assert len(tt.patterns) == 1
    pattern = tt.patterns[0]
    assert pattern.stops == ["S1", "S2"]
    # One trip: S1 dep 08:00, S2 arr 08:10.
    assert pattern.dep[0, 0] == 8 * 3600
    assert pattern.arr[0, 1] == 8 * 3600 + 600


def test_raptor_finds_single_leg_journey():
    tt = build_timetable(load_gtfs(GTFS_DIR))
    # Board at S1 at 08:00 (arrival there = departure, zero access).
    labels = raptor(tt, {"S1": (8 * 3600, 0.0)})
    assert "S2" in labels
    assert labels["S2"].arrival == 8 * 3600 + 600
    assert labels["S2"].ivt == 600
    assert labels["S2"].boardings == 1


def test_raptor_no_reverse_path():
    tt = build_timetable(load_gtfs(GTFS_DIR))
    # The only trip runs S1→S2; from S2 you cannot reach S1 by transit.
    labels = raptor(tt, {"S2": (8 * 3600, 0.0)})
    assert "S1" not in labels or labels["S1"].boardings == 0


def test_compute_transit_skims_decomposition():
    tt = build_timetable(load_gtfs(GTFS_DIR))
    skims = compute_transit_skims(tt, ZONES, departure_sec=8 * 3600)

    # Only the forward S1→S2 (zone1→zone2) journey is served.
    assert set(zip(skims["origin_zone"], skims["dest_zone"], strict=True)) == {
        ("060830001001", "060830001002")
    }
    row = skims.iloc[0]
    assert row["mode"] == "transit"
    assert row["ivt_min"] == pytest.approx(10.0)  # 08:00 → 08:10
    assert row["n_transfers"] == 0
    assert row["access_min"] == pytest.approx(0.0, abs=1e-6)  # centroid == stop
    assert row["egress_min"] == pytest.approx(0.0, abs=1e-6)
    # Total time decomposes into its parts.
    parts = row[["access_min", "egress_min", "ivt_min", "wait_min", "xfer_walk_min"]].sum()
    assert row["total_time_min"] == pytest.approx(parts, abs=1e-6)


def test_compute_transit_skims_requires_centroids():
    tt = build_timetable(load_gtfs(GTFS_DIR))
    with pytest.raises(ValueError, match="centroid"):
        compute_transit_skims(tt, pd.DataFrame({"zone_id": ["a"]}))


def test_raptor_respects_departure_time():
    # A later departure misses the 08:00 trip → unreachable.
    tt = build_timetable(load_gtfs(GTFS_DIR))
    labels = raptor(tt, {"S1": (9 * 3600, 0.0)})
    assert "S2" not in labels


def test_earliest_trip_picks_next_departure():
    # Two trips on one pattern; ensure RAPTOR boards the first feasible one.
    pattern = Pattern(
        stops=["A", "B"],
        dep=np.array([[100.0, 200.0], [500.0, 600.0]]),
        arr=np.array([[100.0, 200.0], [500.0, 600.0]]),
    )
    from sbcabm.skims.transit import Timetable

    tt = Timetable(
        patterns=[pattern],
        routes_by_stop={"A": [(0, 0)], "B": [(0, 1)]},
        transfers={"A": [], "B": []},
        stop_coords={"A": (0.0, 0.0), "B": (0.0, 0.1)},
    )
    labels = raptor(tt, {"A": (300.0, 0.0)})  # after trip 0, before trip 1
    assert labels["B"].arrival == 600.0  # boards the 500-departing trip


def _offline_pipeline():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config)


def test_transit_skims_stage_runs_offline():
    store = _offline_pipeline().run(
        ["ingest", "zones", "network", "transit_skims"]
    )
    assert store.has("transit_skims")
    transit = store.get("transit_skims")
    assert len(transit) == 1
    assert transit.iloc[0]["ivt_min"] == pytest.approx(10.0)
