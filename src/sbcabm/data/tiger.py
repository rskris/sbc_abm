"""TIGER/Line polygon geometry for the zone system.

The Census Gazetteer (``geographies.py``) gives centroids and area as plain
tables, but a full model also needs the zone *polygons* themselves — for
mapping, point-in-polygon assignment, and especially **adjacency** (which zones
share a boundary), which spatial and network models rely on.

This module reads TIGER/Line block-group geometry and derives:

* standardized zone geometries (``zone_id`` + polygon, in geographic CRS),
* geometric centroids and land area (computed in a projected CRS for accuracy),
* a zone adjacency (contiguity) edge list.

``geopandas``/``shapely``/``pyproj`` (the ``geo`` extra) are imported lazily, so
importing this module — and the rest of the package — never requires them. Call
a function without the extra installed and you get a clear error.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("sbcabm.data.tiger")

# 1 square mile = 27,878,400 square US-survey feet (EPSG:2229 units).
_SQFT_PER_SQMI = 27_878_400.0


def _require_geo():
    try:
        import geopandas as gpd  # noqa: F401
        import shapely  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "TIGER polygon support needs the 'geo' extra: pip install 'sbcabm[geo]'"
        ) from exc
    import geopandas as gpd

    return gpd


def geodataframe_from_wkt(
    df: pd.DataFrame,
    *,
    geoid_col: str = "GEOID",
    wkt_col: str = "geometry",
    crs: str = "EPSG:4326",
):
    """Build a GeoDataFrame from a table whose geometry is WKT text.

    Lets geometry travel as a plain, version-controllable CSV (used for
    fixtures) while still producing a real GeoDataFrame.
    """
    gpd = _require_geo()
    from shapely import wkt

    geometry = df[wkt_col].apply(wkt.loads)
    attrs = df.drop(columns=[wkt_col])
    return gpd.GeoDataFrame(attrs, geometry=geometry, crs=crs)


def read_block_group_shapefile(path: str):
    """Read a TIGER/Line block-group shapefile or zip into a GeoDataFrame."""
    gpd = _require_geo()
    return gpd.read_file(path)


def clip_to_county(gdf, county_geoid: str, *, geoid_col: str = "GEOID"):
    """Keep only block groups whose GEOID falls within ``county_geoid`` (5 digits)."""
    in_county = gdf[geoid_col].astype(str).str[:5] == county_geoid
    return gdf.loc[in_county].copy()


def standardize_geometries(gdf, *, geoid_col: str = "GEOID", geographic_crs: str = "EPSG:4326"):
    """Return a tidy ``zone_id`` + ``geometry`` GeoDataFrame in geographic CRS."""
    gpd = _require_geo()
    out = gdf[[geoid_col, gdf.geometry.name]].copy()
    out = out.rename(columns={geoid_col: "zone_id"})
    out["zone_id"] = out["zone_id"].astype(str)
    geo = gpd.GeoDataFrame(out, geometry=gdf.geometry.name, crs=gdf.crs)
    if geo.crs is not None and str(geo.crs) != geographic_crs:
        geo = geo.to_crs(geographic_crs)
    return geo


def zone_geometry_attributes(
    gdf,
    *,
    working_crs: str,
    geographic_crs: str = "EPSG:4326",
    geoid_col: str = "GEOID",
) -> pd.DataFrame:
    """Compute centroid (lon/lat) and land area (sq mi) from polygons.

    Areas and centroids are computed in ``working_crs`` (a projected CRS, e.g.
    California State Plane in feet) for geometric accuracy; the centroid point is
    then expressed back in ``geographic_crs`` for storage as ``centroid_x``
    (longitude) / ``centroid_y`` (latitude).
    """
    _require_geo()
    index = pd.Index(gdf[geoid_col].astype(str), name="zone_id")
    projected = gdf.to_crs(working_crs)

    area_sqmi = projected.geometry.area / _SQFT_PER_SQMI
    centroids_geo = projected.geometry.centroid.to_crs(geographic_crs)

    out = pd.DataFrame(index=index)
    out["centroid_x"] = centroids_geo.x.to_numpy()
    out["centroid_y"] = centroids_geo.y.to_numpy()
    out["area_land_sqmi"] = area_sqmi.to_numpy()
    return out


def build_adjacency(gdf, *, geoid_col: str = "GEOID") -> pd.DataFrame:
    """Build a zone adjacency (queen contiguity) edge list from polygons.

    Returns a long-form DataFrame of ``zone_id``/``neighbor_id`` pairs for zones
    that share a boundary. Each adjacency appears in both directions.
    """
    gpd = _require_geo()
    zones = gdf[[geoid_col, gdf.geometry.name]].copy()
    zones[geoid_col] = zones[geoid_col].astype(str)
    zones = gpd.GeoDataFrame(zones, geometry=gdf.geometry.name, crs=gdf.crs)

    pairs = gpd.sjoin(zones, zones, predicate="touches", how="inner")
    left = f"{geoid_col}_left"
    right = f"{geoid_col}_right"
    edges = pairs[[left, right]].rename(
        columns={left: "zone_id", right: "neighbor_id"}
    )
    edges = edges[edges["zone_id"] != edges["neighbor_id"]]
    edges = edges.drop_duplicates().reset_index(drop=True)
    logger.info("built zone adjacency: %d edges over %d zones", len(edges), len(zones))
    return edges
