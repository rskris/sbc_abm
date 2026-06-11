"""Tests for story 6.1 — static BPR assignment (MSA)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sbcabm.assignment.static import assign_static
from sbcabm.config import load_config
from sbcabm.network.graph import Network
from sbcabm.pipeline import build_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"
NET_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "network"


def _network() -> Network:
    nodes = pd.read_csv(NET_FIXTURES / "network_nodes.csv", dtype={"node_id": str})
    links = pd.read_csv(
        NET_FIXTURES / "network_links.csv", dtype={"from_node": str, "to_node": str}
    )
    return Network.from_tables(nodes, links)


def _connectors() -> pd.DataFrame:
    return pd.DataFrame(
        {"zone_id": ["z1", "z2"], "node_id": ["D", "A"], "connector_mi": [0.0, 0.0]}
    )


def _trips(n: int = 40, mode: str = "drive_alone", depart: float = 8.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trip_id": range(n),
            "origin_zone": ["z1"] * n,
            "dest_zone": ["z2"] * n,
            "mode": [mode] * n,
            "depart_hour": [depart] * n,
        }
    )


def test_trip_conservation_per_period():
    # 40 AM + 10 MD auto trips, plus walk trips that must be ignored.
    trips = pd.concat(
        [
            _trips(40, depart=8.0),
            _trips(10, mode="shared_ride", depart=12.0),
            _trips(5, mode="walk", depart=8.0),
        ],
        ignore_index=True,
    )
    result = assign_static(trips, _network(), _connectors())
    diag = result.diagnostics.set_index("period")
    assert diag.loc["AM", "vehicle_trips_routed"] == pytest.approx(40.0)
    assert diag.loc["MD", "vehicle_trips_routed"] == pytest.approx(10.0)
    assert set(diag.index) == {"AM", "MD"}  # walk never assigned


def test_occupancy_divides_vehicle_trips():
    trips = _trips(40, mode="shared_ride")
    result = assign_static(
        trips, _network(), _connectors(), occupancy={"drive_alone": 1.0, "shared_ride": 2.0}
    )
    # 40 person-trips at occupancy 2 → 20 vehicle trips on every traversed link.
    diag = result.diagnostics.set_index("period")
    assert diag.loc["AM", "vehicle_trips_routed"] == pytest.approx(20.0)
    loaded = result.link_volumes.query("volume > 0")
    assert np.allclose(loaded["volume"], 20.0)


def test_congested_time_at_least_free_flow_and_strictly_greater_when_loaded():
    result = assign_static(_trips(200), _network(), _connectors())
    ct = result.congested_times.merge(
        result.link_volumes, on=["from_node", "to_node", "period"]
    )
    assert (ct["time_min"] >= ct["free_flow_min"] - 1e-12).all()
    loaded = ct[ct["volume"] > 0]
    assert len(loaded) > 0
    assert (loaded["time_min"] > loaded["free_flow_min"]).all()


def test_msa_converges_with_diagnostics():
    result = assign_static(_trips(100), _network(), _connectors())
    diag = result.diagnostics
    assert diag["converged"].all()
    assert (diag["relative_gap"] < 1e-3).all()
    assert (diag["iterations"] <= 20).all()


def test_deterministic():
    a = assign_static(_trips(60), _network(), _connectors())
    b = assign_static(_trips(60), _network(), _connectors())
    pd.testing.assert_frame_equal(a.link_volumes, b.link_volumes)
    pd.testing.assert_frame_equal(a.congested_times, b.congested_times)


def test_bpr_responds_to_volume():
    # Heavier demand on the same OD must produce slower congested times.
    light = assign_static(_trips(10), _network(), _connectors())
    heavy = assign_static(_trips(2000), _network(), _connectors())
    key = ["from_node", "to_node", "period"]
    merged = light.congested_times.merge(heavy.congested_times, on=key, suffixes=("_l", "_h"))
    loaded = merged[merged["time_min_h"] > merged["free_flow_min_h"]]
    assert (loaded["time_min_h"] >= loaded["time_min_l"]).all()
    assert (loaded["time_min_h"] > loaded["time_min_l"]).any()


def test_intrazonal_trips_route_with_zero_links():
    # Same zone → same connector node → counted as routed, no link volume.
    trips = pd.DataFrame(
        {
            "trip_id": [0],
            "origin_zone": ["z1"],
            "dest_zone": ["z1"],
            "mode": ["drive_alone"],
            "depart_hour": [8.0],
        }
    )
    result = assign_static(trips, _network(), _connectors())
    assert result.diagnostics["vehicle_trips_routed"].sum() == pytest.approx(1.0)
    assert (result.link_volumes["volume"] == 0).all()


def _offline_pipeline():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config)


def test_assignment_stage_runs_offline():
    store = _offline_pipeline().run()
    for table in ("link_volumes", "congested_times", "assignment_diagnostics"):
        assert store.has(table)
    diag = store.get("assignment_diagnostics")
    assert diag["converged"].all()
    # Every auto trip in the trip list got routed.
    trips = store.get("trips")
    auto = trips[trips["mode"].isin(("drive_alone", "shared_ride"))]
    assert diag["vehicle_trips_routed"].sum() == pytest.approx(len(auto))


def test_assignment_requires_trips():
    with pytest.raises(KeyError, match="assignment requires"):
        _offline_pipeline().run(["assignment"])
