"""Build the network tables from OpenStreetMap (best-effort).

``osmnx`` (the ``osm`` extra) is imported lazily so the package never requires
it. This produces a first-cut multimodal network: every drivable link allows
auto, and also walk/bike except on motorway/trunk classes. Speeds come from the
OSM ``maxspeed`` tag where present, else a per-class default. Refine for
production; the skim machinery itself is independent of this builder.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("sbcabm.network.build")

# Default free-flow speeds (mph) by OSM highway class.
_CLASS_SPEED = {
    "motorway": 65,
    "trunk": 55,
    "primary": 45,
    "secondary": 35,
    "tertiary": 30,
    "residential": 25,
    "unclassified": 25,
    "service": 15,
}
_NO_ACTIVE = {"motorway", "trunk", "motorway_link", "trunk_link"}
_METERS_PER_MILE = 1609.34


def _require_osmnx():
    try:
        import osmnx as ox
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "OSM network ingestion needs the 'osm' extra: pip install 'sbcabm[osm]'"
        ) from exc
    return ox


def from_osm(
    *, place: str | None = None, polygon=None, default_speed_mph: float = 25.0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Download a drivable network and convert it to node/link tables."""
    ox = _require_osmnx()
    if polygon is not None:
        graph = ox.graph_from_polygon(polygon, network_type="drive")
    elif place is not None:
        graph = ox.graph_from_place(place, network_type="drive")
    else:
        raise ValueError("from_osm requires either 'place' or 'polygon'")
    return graph_to_tables(graph, default_speed_mph=default_speed_mph)


def graph_to_tables(graph, *, default_speed_mph: float = 25.0):
    """Convert an osmnx/networkx graph into ``network_nodes``/``network_links``."""
    node_rows = [
        (node_id, float(data.get("x")), float(data.get("y")))
        for node_id, data in graph.nodes(data=True)
    ]
    nodes = pd.DataFrame(node_rows, columns=["node_id", "x", "y"])

    link_rows = []
    for u, v, data in graph.edges(data=True):
        highway = _first(data.get("highway"))
        length_mi = float(data.get("length", 0.0)) / _METERS_PER_MILE
        speed = _parse_speed(data.get("maxspeed")) or _CLASS_SPEED.get(
            highway, default_speed_mph
        )
        active = highway not in _NO_ACTIVE
        link_rows.append(
            (
                u,
                v,
                length_mi,
                float(speed),
                True,  # allow_drive
                active,  # allow_walk
                active,  # allow_bike
                bool(data.get("oneway", False)),
            )
        )
    links = pd.DataFrame(
        link_rows,
        columns=[
            "from_node",
            "to_node",
            "length_mi",
            "speed_mph",
            "allow_drive",
            "allow_walk",
            "allow_bike",
            "oneway",
        ],
    )
    logger.info("converted OSM graph: %d nodes, %d links", len(nodes), len(links))
    return nodes, links


def _first(value):
    """OSM tags are sometimes lists; take the first element."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _parse_speed(value) -> float | None:
    value = _first(value)
    if value is None:
        return None
    try:
        return float(str(value).split()[0])  # handles "35 mph"
    except (ValueError, IndexError):
        return None
