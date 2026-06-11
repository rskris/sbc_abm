"""The :class:`Network` — a multimodal routable graph over two tidy tables.

* ``network_nodes``: ``node_id``, ``x`` (lon), ``y`` (lat).
* ``network_links``: ``from_node``, ``to_node``, ``length_mi``, ``speed_mph``,
  ``allow_drive``, ``allow_walk``, ``allow_bike`` and ``oneway``.

A two-way link (``oneway`` false) is materialized as edges in both directions.
``mode_graph`` returns a ``networkx`` digraph filtered to one mode, with a
``time_min`` weight either from the link's own speed (auto) or a constant mode
speed (walk/bike).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

NODE_COLUMNS = ("node_id", "x", "y")
LINK_COLUMNS = (
    "from_node",
    "to_node",
    "length_mi",
    "speed_mph",
    "allow_drive",
    "allow_walk",
    "allow_bike",
)

_MODE_FLAG = {"drive": "allow_drive", "walk": "allow_walk", "bike": "allow_bike"}


class Network:
    def __init__(self, nodes: pd.DataFrame, links: pd.DataFrame) -> None:
        for col in NODE_COLUMNS:
            if col not in nodes.columns:
                raise ValueError(f"network_nodes is missing column '{col}'")
        for col in LINK_COLUMNS:
            if col not in links.columns:
                raise ValueError(f"network_links is missing column '{col}'")
        if nodes["node_id"].duplicated().any():
            raise ValueError("node_id values must be unique")

        self.nodes = nodes.reset_index(drop=True)
        self.links = links.reset_index(drop=True)
        self._coords = self.nodes.set_index("node_id")[["x", "y"]]

    def __len__(self) -> int:
        return len(self.nodes)

    def mode_graph(self, mode: str, *, speed_mph: float | None = None):
        """Return a ``networkx.DiGraph`` for ``mode``.

        Edges are kept where the mode is allowed. ``time_min`` is computed from
        each link's own ``speed_mph`` when ``speed_mph`` is ``None`` (auto), or
        from the constant ``speed_mph`` for walk/bike. Two-way links contribute
        both directions.
        """
        import networkx as nx

        if mode not in _MODE_FLAG:
            raise ValueError(f"unknown mode '{mode}'; expected one of {list(_MODE_FLAG)}")
        flag = _MODE_FLAG[mode]

        allowed = self.links[self.links[flag].astype(bool)]
        speed = (
            np.full(len(allowed), float(speed_mph))
            if speed_mph is not None
            else allowed["speed_mph"].to_numpy(dtype=float)
        )
        length = allowed["length_mi"].to_numpy(dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            time_min = np.where(speed > 0, length / speed * 60.0, np.inf)

        graph = nx.DiGraph()
        graph.add_nodes_from(self.nodes["node_id"].tolist())
        oneway = (
            allowed["oneway"].astype(bool).to_numpy()
            if "oneway" in allowed.columns
            else np.zeros(len(allowed), dtype=bool)
        )
        fro = allowed["from_node"].to_numpy()
        to = allowed["to_node"].to_numpy()
        for i in range(len(allowed)):
            attrs = {"time_min": float(time_min[i]), "length_mi": float(length[i])}
            graph.add_edge(fro[i], to[i], **attrs)
            if not oneway[i]:
                graph.add_edge(to[i], fro[i], **attrs)
        return graph

    def nearest_node(self, x: float, y: float):
        """Return the id of the node closest to ``(x, y)`` (Euclidean in lon/lat)."""
        dx = self._coords["x"].to_numpy() - x
        dy = self._coords["y"].to_numpy() - y
        idx = int(np.argmin(dx * dx + dy * dy))
        return self._coords.index[idx]

    @classmethod
    def from_tables(cls, nodes: pd.DataFrame, links: pd.DataFrame) -> Network:
        return cls(nodes, links)
