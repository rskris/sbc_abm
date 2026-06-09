"""Tests for TIGER polygon geometry: attributes, adjacency, and zone wiring.

Skipped entirely when the optional ``geo`` extra (geopandas) is not installed.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("geopandas")

from sbcabm.config import load_config  # noqa: E402
from sbcabm.data import tiger  # noqa: E402
from sbcabm.pipeline import build_pipeline  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"
GEOM_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "census" / "block_group_geometries.csv"


def _fixture_gdf():
    df = pd.read_csv(GEOM_FIXTURE, dtype={"GEOID": str})
    return tiger.geodataframe_from_wkt(df)


def test_geodataframe_from_wkt_builds_geometry():
    gdf = _fixture_gdf()
    assert gdf.crs is not None
    assert gdf.geometry.geom_type.eq("Polygon").all()
    assert list(gdf["GEOID"]) == ["060830001001", "060830001002"]


def test_clip_to_county_filters_by_geoid_prefix():
    gdf = _fixture_gdf()
    kept = tiger.clip_to_county(gdf, "06083")
    assert len(kept) == 2
    dropped = tiger.clip_to_county(gdf, "06999")
    assert len(dropped) == 0


def test_standardize_geometries_renames_and_reprojects():
    gdf = tiger.standardize_geometries(_fixture_gdf())
    assert "zone_id" in gdf.columns
    assert "GEOID" not in gdf.columns
    assert str(gdf.crs).upper().endswith("4326")


def test_zone_geometry_attributes_centroid_and_area():
    gdf = tiger.standardize_geometries(_fixture_gdf())
    attrs = tiger.zone_geometry_attributes(
        gdf, working_crs="EPSG:2229", geoid_col="zone_id"
    )
    z1 = attrs.loc["060830001001"]
    # West polygon spans lon [-119.71, -119.70]; centroid near -119.705.
    assert z1["centroid_x"] == pytest.approx(-119.705, abs=1e-3)
    assert z1["centroid_y"] == pytest.approx(34.42, abs=1e-3)
    assert z1["area_land_sqmi"] > 0


def test_build_adjacency_finds_shared_edge():
    gdf = tiger.standardize_geometries(_fixture_gdf())
    edges = tiger.build_adjacency(gdf, geoid_col="zone_id")
    # The two polygons share an edge → mutual adjacency, both directions.
    assert len(edges) == 2
    pairs = set(map(tuple, edges[["zone_id", "neighbor_id"]].to_numpy()))
    assert ("060830001001", "060830001002") in pairs
    assert ("060830001002", "060830001001") in pairs


def _offline_pipeline():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config)


def test_zones_stage_produces_geometry_and_adjacency():
    store = _offline_pipeline().run(["ingest", "zones"])
    assert store.has("block_group_geometries")
    assert store.has("zone_geometries")
    assert store.has("zone_adjacency")

    adjacency = store.get("zone_adjacency")
    assert len(adjacency) == 2  # the two block groups are neighbors

    # Gazetteer still wins for the centroid (its official internal point),
    # so geometry presence does not override the gazetteer-derived centroid.
    zones = store.get("zones").set_index("zone_id")
    assert zones.loc["060830001001", "centroid_y"] == 34.42
