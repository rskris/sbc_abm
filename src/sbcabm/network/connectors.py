"""Centroid connectors: link each zone to the network.

A zone's travel begins and ends at its centroid, which is not itself a network
node. A *centroid connector* ties the zone to its nearest network node, with an
access/egress distance used to add local access time to skims.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .graph import Network

# Rough miles per degree of latitude; longitude scaled by cos(lat). Good enough
# for short centroid-to-node access distances.
_MILES_PER_DEG_LAT = 69.0


def connect_zones(network: Network, zones: pd.DataFrame) -> pd.DataFrame:
    """Map each zone centroid to its nearest network node.

    ``zones`` must carry ``zone_id`` and centroid coordinates ``centroid_x``
    (lon) / ``centroid_y`` (lat). Returns ``zone_id``, ``node_id`` and
    ``connector_mi`` (great-circle-ish access distance in miles).
    """
    required = {"zone_id", "centroid_x", "centroid_y"}
    missing = required - set(zones.columns)
    if missing:
        raise ValueError(f"zones is missing centroid columns: {sorted(missing)}")

    records = []
    coords = network.nodes.set_index("node_id")[["x", "y"]]
    node_x = coords["x"].to_numpy()
    node_y = coords["y"].to_numpy()
    node_ids = coords.index.to_numpy()

    for row in zones.itertuples(index=False):
        zx, zy = float(row.centroid_x), float(row.centroid_y)
        scale = np.cos(np.radians(zy))
        dx = (node_x - zx) * scale
        dy = node_y - zy
        d2 = dx * dx + dy * dy
        idx = int(np.argmin(d2))
        connector_mi = float(np.sqrt(d2[idx]) * _MILES_PER_DEG_LAT)
        records.append((row.zone_id, node_ids[idx], connector_mi))

    return pd.DataFrame(records, columns=["zone_id", "node_id", "connector_mi"])
