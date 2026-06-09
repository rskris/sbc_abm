"""The ``zones`` pipeline stage: build the model zone table.

Default model zones are Census block groups (acting as TAZs). This stage derives
a tidy ``zones`` table from the ingested ACS block-group data — zone id plus
baseline attributes — which downstream models join against. Geometry-backed
attributes (centroids, area, adjacency) are layered on later via the ``geo``
extra without changing the table's contract.
"""

from __future__ import annotations

import logging

import pandas as pd

from ..config import Config
from ..pipeline import DataStore
from .zone_system import ZoneSystem

logger = logging.getLogger("sbcabm.zones")

# ACS variable → friendly zone attribute name.
_ATTRIBUTES = {
    "B11016_001E": "total_households",
}


def run_zones(config: Config, store: DataStore) -> None:
    if not store.has("acs_block_groups"):
        raise KeyError("zones stage requires 'acs_block_groups'; run 'ingest' first")

    acs = store.get("acs_block_groups")
    if "GEOID" not in acs.columns:
        raise KeyError("acs_block_groups is missing the 'GEOID' identifier")

    zones = pd.DataFrame({"zone_id": acs["GEOID"].astype(str)})
    for acs_var, attr in _ATTRIBUTES.items():
        if acs_var in acs.columns:
            zones[attr] = pd.to_numeric(acs[acs_var], errors="coerce").fillna(0)

    # Validate via ZoneSystem (unique ids, required columns) before storing.
    ZoneSystem.from_frame(zones)
    store.put("zones", zones)
    logger.info("built zone system with %d zones (%s)", len(zones), config.zones.system)
