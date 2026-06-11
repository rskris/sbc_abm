"""Tests for story 6.5 — network summary rollup."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sbcabm.assignment.static import assign_static
from sbcabm.assignment.summary import network_summary
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


def test_vmt_vht_consistency():
    # 10 AM drive_alone trips over the 1.9-mile A..D path.
    trips = pd.DataFrame(
        {
            "trip_id": range(10),
            "origin_zone": ["z2"] * 10,
            "dest_zone": ["z1"] * 10,
            "mode": ["drive_alone"] * 10,
            "depart_hour": [8.0] * 10,
        }
    )
    network = _network()
    result = assign_static(trips, network, _connectors())
    summary = network_summary(result.link_volumes, result.congested_times, network)

    am = summary.set_index("period").loc["AM"]
    # VMT = 10 vehicles × 1.9 path miles (light load; one path).
    assert am["vmt"] == pytest.approx(19.0, rel=1e-3)
    # VHT consistent with VMT and average speed.
    assert am["avg_speed_mph"] == pytest.approx(am["vmt"] / am["vht"], rel=1e-9)
    # Light load → congestion ratio barely above 1.
    assert 1.0 <= am["congestion_ratio"] < 1.1


def test_summary_in_pipeline_and_equilibrium():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    store = build_pipeline(config).run()

    summary = store.get("network_summary")
    assert {"period", "vmt", "vht", "avg_speed_mph", "congestion_ratio"}.issubset(
        summary.columns
    )
    assert (summary["vmt"] >= 0).all()
    assert (summary["congestion_ratio"] >= 1.0 - 1e-12).all()
    # Equilibrium history (6.2) carries the per-iteration convergence metrics.
    history = store.get("equilibrium_history")
    assert {"iteration", "skim_rmse", "mean_assignment_gap"}.issubset(history.columns)
