"""Tests for skim computation and the network → skims pipeline stages."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sbcabm.config import load_config
from sbcabm.network.graph import Network
from sbcabm.pipeline import build_pipeline
from sbcabm.skims.skims import compute_skims

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"
NET_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "network"


def _fixture_network() -> Network:
    nodes = pd.read_csv(NET_FIXTURES / "network_nodes.csv", dtype={"node_id": str})
    links = pd.read_csv(
        NET_FIXTURES / "network_links.csv", dtype={"from_node": str, "to_node": str}
    )
    return Network.from_tables(nodes, links)


def _connectors() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "zone_id": ["z1", "z2"],
            "node_id": ["D", "A"],  # z1 near D, z2 near A
            "connector_mi": [0.0, 0.0],
        }
    )


def test_skims_cover_all_pairs_and_modes():
    skims = compute_skims(_fixture_network(), _connectors())
    # 2 zones × 2 zones × 3 modes × 1 period = 12 records.
    assert len(skims) == 12
    assert set(skims["mode"]) == {"auto", "walk", "bike"}
    assert set(skims["origin_zone"]) == {"z1", "z2"}


def test_auto_faster_than_bike_faster_than_walk():
    skims = compute_skims(_fixture_network(), _connectors())
    od = skims[(skims["origin_zone"] == "z2") & (skims["dest_zone"] == "z1")]
    by_mode = od.set_index("mode")["time_min"]
    assert by_mode["auto"] < by_mode["bike"] < by_mode["walk"]
    # A→D is 0.6+0.7+0.6 = 1.9 miles of network.
    assert od.set_index("mode").loc["auto", "dist_mi"] == pytest.approx(1.9)


def test_intrazonal_is_small_and_present():
    skims = compute_skims(_fixture_network(), _connectors())
    intra = skims[(skims["origin_zone"] == "z1") & (skims["dest_zone"] == "z1")]
    assert len(intra) == 3  # one per mode
    # With zero-length connectors here, intrazonal time is ~0 and non-negative.
    assert (intra["time_min"] >= 0).all()
    assert (intra["dist_mi"] >= 0).all()


def _offline_pipeline():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config)


def test_network_and_skims_stages_run_offline():
    store = _offline_pipeline().run(["ingest", "zones", "network", "skims"])
    assert store.has("network_nodes")
    assert store.has("zone_connectors")
    assert store.has("skims")

    skims = store.get("skims")
    # 2 zones in the fixtures × 2 × 3 modes.
    assert len(skims) == 12
    assert (skims["time_min"] >= 0).all()

    # Centroid connectors mapped the two block groups onto the network.
    connectors = store.get("zone_connectors")
    assert set(connectors["zone_id"]) == {"060830001001", "060830001002"}


def test_skims_stage_requires_network():
    config = load_config(CONFIG)
    pipeline = build_pipeline(config)
    with pytest.raises(KeyError, match="skims stage requires"):
        pipeline.run(["skims"])
