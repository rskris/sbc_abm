"""Tests for the multimodal network graph and centroid connectors."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd
import pytest

from sbcabm.network.build import graph_to_tables
from sbcabm.network.connectors import connect_zones
from sbcabm.network.graph import Network

REPO_ROOT = Path(__file__).resolve().parents[1]
NET_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "network"


def _fixture_network() -> Network:
    nodes = pd.read_csv(NET_FIXTURES / "network_nodes.csv", dtype={"node_id": str})
    links = pd.read_csv(
        NET_FIXTURES / "network_links.csv", dtype={"from_node": str, "to_node": str}
    )
    return Network.from_tables(nodes, links)


def test_mode_graph_builds_bidirectional_edges():
    net = _fixture_network()
    drive = net.mode_graph("drive")
    # 3 two-way links → 6 directed edges.
    assert drive.number_of_edges() == 6
    # A→B time at 30 mph over 0.6 mi = 1.2 minutes.
    assert drive["A"]["B"]["time_min"] == pytest.approx(0.6 / 30 * 60)


def test_mode_graph_constant_speed_for_active_modes():
    net = _fixture_network()
    walk = net.mode_graph("walk", speed_mph=3.0)
    assert walk["A"]["B"]["time_min"] == pytest.approx(0.6 / 3.0 * 60)


def test_mode_graph_rejects_unknown_mode():
    with pytest.raises(ValueError, match="unknown mode"):
        _fixture_network().mode_graph("teleport")


def test_nearest_node():
    net = _fixture_network()
    assert net.nearest_node(-119.70, 34.42) == "D"
    assert net.nearest_node(-119.72, 34.43) == "A"


def test_connect_zones_maps_centroids_to_nodes():
    net = _fixture_network()
    zones = pd.DataFrame(
        {
            "zone_id": ["060830001001", "060830001002"],
            "centroid_x": [-119.70, -119.72],
            "centroid_y": [34.42, 34.43],
        }
    )
    connectors = connect_zones(net, zones)
    mapping = dict(zip(connectors["zone_id"], connectors["node_id"], strict=True))
    assert mapping["060830001001"] == "D"
    assert mapping["060830001002"] == "A"
    assert (connectors["connector_mi"] >= 0).all()


def test_connect_zones_requires_centroids():
    net = _fixture_network()
    with pytest.raises(ValueError, match="centroid"):
        connect_zones(net, pd.DataFrame({"zone_id": ["a"]}))


def test_graph_to_tables_from_osm_like_graph():
    g = nx.DiGraph()
    g.add_node(1, x=-119.7, y=34.4)
    g.add_node(2, x=-119.6, y=34.4)
    g.add_edge(1, 2, length=1609.34, highway="residential", oneway=False)
    g.add_edge(2, 1, length=1609.34, highway="motorway", oneway=True)
    nodes, links = graph_to_tables(g)
    assert len(nodes) == 2
    assert links.loc[0, "length_mi"] == pytest.approx(1.0, rel=1e-3)
    # residential default speed and active modes allowed.
    assert links.loc[0, "allow_walk"]
    # motorway disallows walk/bike.
    assert not links.loc[1, "allow_bike"]


def test_network_validates_columns():
    with pytest.raises(ValueError, match="network_links is missing"):
        Network(pd.DataFrame({"node_id": [1], "x": [0], "y": [0]}), pd.DataFrame())
