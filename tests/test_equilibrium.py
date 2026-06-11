"""Tests for story 6.2 — congested skims and the equilibrium loop."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sbcabm.assignment.static import assign_static
from sbcabm.config import load_config
from sbcabm.network.graph import Network
from sbcabm.pipeline import build_pipeline
from sbcabm.skims.congested import collapse_to_representative, congested_auto_skims

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


def _base_auto_skim() -> pd.DataFrame:
    rows = [
        ("z1", "z1", "auto", "free_flow", 0.0, 0.0),
        ("z1", "z2", "auto", "free_flow", 4.04, 1.9),
        ("z2", "z1", "auto", "free_flow", 4.04, 1.9),
        ("z2", "z2", "auto", "free_flow", 0.0, 0.0),
    ]
    return pd.DataFrame(
        rows, columns=["origin_zone", "dest_zone", "mode", "time_period", "time_min", "dist_mi"]
    )


def _heavy_trips(n: int = 3000) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trip_id": range(n),
            "origin_zone": ["z2"] * n,
            "dest_zone": ["z1"] * n,
            "mode": ["drive_alone"] * n,
            "depart_hour": [8.0] * n,
        }
    )


def test_congested_skims_slower_than_free_flow_under_load():
    result = assign_static(_heavy_trips(), _network(), _connectors())
    skims = congested_auto_skims(result.congested_times, _connectors(), _base_auto_skim())

    am = skims[skims["time_period"] == "AM"].set_index(["origin_zone", "dest_zone"])
    # The loaded direction is slower than free flow (4.04 min), distance carried over.
    assert am.loc[("z2", "z1"), "time_min"] > 4.04
    assert am.loc[("z2", "z1"), "dist_mi"] == pytest.approx(1.9)


def test_collapse_to_representative_means_periods():
    per_period = pd.DataFrame(
        {
            "origin_zone": ["z1", "z1"],
            "dest_zone": ["z2", "z2"],
            "mode": ["auto", "auto"],
            "time_period": ["AM", "PM"],
            "time_min": [10.0, 20.0],
            "dist_mi": [1.9, 1.9],
        }
    )
    rep = collapse_to_representative(per_period)
    assert len(rep) == 1
    assert rep.iloc[0]["time_min"] == pytest.approx(15.0)
    assert rep.iloc[0]["time_period"] == "congested"


def _offline_pipeline():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config)


def test_equilibrium_stage_history_and_convergence():
    store = _offline_pipeline().run()
    history = store.get("equilibrium_history")
    assert len(history) == 3  # configured iterations
    # The convergence metric does not increase across iterations.
    rmse = history["skim_rmse"].to_numpy()
    assert rmse[-1] <= rmse[0] + 1e-12
    # The auto skim has been replaced by the congested representative.
    auto = store.get("skims").query("mode == 'auto'")
    assert set(auto["time_period"].unique()) == {"congested"}


def test_equilibrium_reproducible_given_seed():
    a = _offline_pipeline().run()
    b = _offline_pipeline().run()
    pd.testing.assert_frame_equal(
        a.get("equilibrium_history"), b.get("equilibrium_history")
    )
    pd.testing.assert_frame_equal(
        a.get("skims").reset_index(drop=True), b.get("skims").reset_index(drop=True)
    )


def test_equilibrium_requires_upstream():
    with pytest.raises(KeyError, match="equilibrium requires"):
        _offline_pipeline().run(["equilibrium"])
