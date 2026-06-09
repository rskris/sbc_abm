"""Tests for LODES employment, Gazetteer geography, and zone enrichment."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sbcabm.config import load_config
from sbcabm.data.employment import aggregate_employment
from sbcabm.data.geographies import parse_gazetteer
from sbcabm.pipeline import build_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"
CENSUS_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "census"


def test_aggregate_employment_rolls_blocks_to_block_groups():
    wac = pd.DataFrame(
        {
            "w_geocode": ["060830001001000", "060830001001001", "060830001002000"],
            "C000": [50, 30, 40],
            "CNS07": [20, 10, 5],  # retail
            "CNS16": [10, 5, 20],  # health
        }
    )
    emp = aggregate_employment(wac)
    assert emp.index.name == "zone_id"
    assert list(emp.index) == ["060830001001", "060830001002"]
    assert emp.loc["060830001001", "emp_total"] == 80
    assert emp.loc["060830001001", "emp_retail"] == 30
    assert emp.loc["060830001001", "emp_health"] == 15
    # A category whose sectors are all absent from the input is zero.
    assert emp.loc["060830001001", "emp_education"] == 0.0


def test_aggregate_employment_requires_id_and_total():
    with pytest.raises(KeyError, match="block id"):
        aggregate_employment(pd.DataFrame({"C000": [1]}))
    with pytest.raises(KeyError, match="total jobs"):
        aggregate_employment(pd.DataFrame({"w_geocode": ["x"]}))


def test_parse_gazetteer_extracts_centroid_and_area():
    gaz = pd.DataFrame(
        {
            "GEOID": ["060830001001"],
            "ALAND_SQMI": [0.5],
            "INTPTLAT": [34.42],
            "INTPTLONG": [-119.70],
        }
    )
    out = parse_gazetteer(gaz)
    assert out.loc["060830001001", "centroid_y"] == 34.42
    assert out.loc["060830001001", "centroid_x"] == -119.70
    assert out.loc["060830001001", "area_land_sqmi"] == 0.5


def test_parse_gazetteer_missing_columns():
    with pytest.raises(KeyError):
        parse_gazetteer(pd.DataFrame({"GEOID": ["x"]}))


def _offline_pipeline():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    return build_pipeline(config)


def test_zones_stage_enriched_with_employment_and_geography():
    store = _offline_pipeline().run(["ingest", "zones"])

    assert store.has("lodes_wac")
    assert store.has("gazetteer")
    zones = store.get("zones")

    z1 = zones.set_index("zone_id").loc["060830001001"]
    assert z1["total_households"] == 30
    assert z1["emp_total"] == 80
    assert z1["emp_retail"] == 30
    # Centroid + area present, and densities derived.
    assert z1["centroid_y"] == 34.42
    assert z1["area_land_sqmi"] == 0.5
    assert z1["emp_density"] == pytest.approx(80 / 0.5)
    assert z1["hh_density"] == pytest.approx(30 / 0.5)


def test_zones_stage_degrades_without_optional_inputs():
    # Provide only the required ACS table; employment/geography stay absent.
    pipeline = _offline_pipeline()
    pipeline.run(["ingest"])
    # Drop optional tables to simulate an ACS-only ingest.
    for name in ("lodes_wac", "gazetteer", "block_group_geometries"):
        pipeline.store._tables.pop(name, None)  # noqa: SLF001 — test introspection
    pipeline.run(["zones"])

    zones = pipeline.store.get("zones")
    assert "total_households" in zones.columns
    assert "emp_total" not in zones.columns
    assert "centroid_x" not in zones.columns
