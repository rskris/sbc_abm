"""The ``zones`` pipeline stage: build the model zone table.

Default model zones are Census block groups (acting as TAZs). This stage derives
a tidy ``zones`` table from ingested data:

* baseline households from the ACS block-group table,
* employment by category from LODES (size terms for destination choice), and
* centroid and land area from the Census Gazetteer (distances and densities).

Employment and geography are merged only when their inputs were ingested, so the
table degrades gracefully. Geometry-backed attributes (polygons, adjacency)
arrive later via the ``geo`` extra without changing this contract.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..config import Config
from ..data.employment import LODES_SECTOR_GROUPS, aggregate_employment
from ..data.geographies import parse_gazetteer
from ..pipeline import DataStore
from .zone_system import ZoneSystem

logger = logging.getLogger("sbcabm.zones")

# ACS variable → friendly zone attribute name.
_ACS_ATTRIBUTES = {
    "B11016_001E": "total_households",
}


def run_zones(config: Config, store: DataStore) -> None:
    if not store.has("acs_block_groups"):
        raise KeyError("zones stage requires 'acs_block_groups'; run 'ingest' first")

    acs = store.get("acs_block_groups")
    if "GEOID" not in acs.columns:
        raise KeyError("acs_block_groups is missing the 'GEOID' identifier")

    zones = pd.DataFrame({"zone_id": acs["GEOID"].astype(str)})
    for acs_var, attr in _ACS_ATTRIBUTES.items():
        if acs_var in acs.columns:
            zones[attr] = pd.to_numeric(acs[acs_var], errors="coerce").fillna(0).to_numpy()

    zones = zones.set_index("zone_id", drop=False)
    zones = _merge_employment(zones, store)
    zones = _merge_geography(zones, store)
    zones = _derive_densities(zones)
    zones = zones.reset_index(drop=True)

    # Validate via ZoneSystem (unique ids, required columns) before storing.
    ZoneSystem.from_frame(zones)
    store.put("zones", zones)
    logger.info(
        "built zone system: %d zones (%s)%s%s",
        len(zones),
        config.zones.system,
        ", +employment" if "emp_total" in zones.columns else "",
        ", +centroids" if "centroid_x" in zones.columns else "",
    )


def _merge_employment(zones: pd.DataFrame, store: DataStore) -> pd.DataFrame:
    if not store.has("lodes_wac"):
        return zones
    emp = aggregate_employment(store.get("lodes_wac"))
    zones = zones.join(emp, how="left")
    emp_cols = ["emp_total", *LODES_SECTOR_GROUPS.keys()]
    zones[emp_cols] = zones[emp_cols].fillna(0.0)
    return zones


def _merge_geography(zones: pd.DataFrame, store: DataStore) -> pd.DataFrame:
    if not store.has("gazetteer"):
        return zones
    geo = parse_gazetteer(store.get("gazetteer"))
    return zones.join(geo, how="left")


def _derive_densities(zones: pd.DataFrame) -> pd.DataFrame:
    """Add per-square-mile densities where the inputs allow."""
    if "area_land_sqmi" not in zones.columns:
        return zones
    area = zones["area_land_sqmi"].replace(0, np.nan)
    if "emp_total" in zones.columns:
        zones["emp_density"] = (zones["emp_total"] / area).fillna(0.0)
    if "total_households" in zones.columns:
        zones["hh_density"] = (zones["total_households"] / area).fillna(0.0)
    return zones
