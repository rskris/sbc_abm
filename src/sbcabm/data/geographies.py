"""Geographic attributes from the Census Gazetteer files.

Full TIGER/Line polygon geometry (and adjacency, routing) belongs to the
optional ``geo`` extra. But the two zonal attributes most models need first —
an internal **centroid** (for straight-line distances and skim seeding) and
**land area** (for densities) — are published in plain tabular form in the
Census *Gazetteer* files, so we can ingest them without geopandas.

The Gazetteer block-group file is tab-delimited with, among others:
``GEOID``, ``ALAND``/``AWATER`` (m²), ``ALAND_SQMI``/``AWATER_SQMI``, and the
internal point ``INTPTLAT`` / ``INTPTLONG``.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("sbcabm.data.geographies")


def parse_gazetteer(
    gazetteer: pd.DataFrame,
    *,
    geoid_col: str = "GEOID",
) -> pd.DataFrame:
    """Extract zone centroid and land area from a Gazetteer block-group table.

    Returns a DataFrame indexed by ``zone_id`` (the GEOID) with:
    ``centroid_x`` (longitude), ``centroid_y`` (latitude) and
    ``area_land_sqmi`` (land area in square miles).
    """
    if geoid_col not in gazetteer.columns:
        raise KeyError(f"gazetteer is missing the '{geoid_col}' column")

    columns = {c.strip(): c for c in gazetteer.columns}

    def pick(*candidates: str) -> str:
        for name in candidates:
            if name in columns:
                return columns[name]
        raise KeyError(f"gazetteer is missing any of columns {candidates}")

    lat_col = pick("INTPTLAT", "intptlat")
    lon_col = pick("INTPTLONG", "INTPTLON", "intptlong")
    area_col = pick("ALAND_SQMI", "aland_sqmi")

    index = pd.Index(gazetteer[geoid_col].astype(str), name="zone_id")
    out = pd.DataFrame(index=index)
    out["centroid_y"] = pd.to_numeric(gazetteer[lat_col], errors="coerce").to_numpy()
    out["centroid_x"] = pd.to_numeric(gazetteer[lon_col], errors="coerce").to_numpy()
    out["area_land_sqmi"] = pd.to_numeric(gazetteer[area_col], errors="coerce").to_numpy()

    logger.info("parsed gazetteer centroids/area for %d zones", len(out))
    return out
