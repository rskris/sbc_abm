"""Tests for configuration loading and the pipeline orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from sbcabm.config import load_config
from sbcabm.pipeline import build_pipeline
from sbcabm.zones import ZoneSystem

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"


def test_loads_default_config():
    config = load_config(CONFIG)
    assert config.region.name == "Santa Barbara County"
    assert config.region.county_geoid == "06083"
    assert config.random_seed == 42
    assert "popsyn" in config.stages


def test_popsyn_stage_runs_from_fixtures(tmp_path):
    config = load_config(CONFIG)
    # Point the run at the repo fixtures explicitly (offline path).
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")

    pipeline = build_pipeline(config)
    store = pipeline.run(["popsyn"])

    assert store.has("households")
    assert store.has("persons")
    assert store.has("popsyn_diagnostics")
    assert len(store.get("households")) == 180  # 100 + 80 from the controls fixture
    assert len(store.get("persons")) > 0


def test_unimplemented_stage_is_skipped():
    config = load_config(CONFIG)
    pipeline = build_pipeline(config)
    # 'assignment' is planned, not implemented — running it must not error.
    store = pipeline.run(["assignment"])
    assert store.names() == []


def test_zone_system_basic():
    import pandas as pd

    zs = ZoneSystem.from_frame(
        pd.DataFrame({"zone_id": ["a", "b"], "households": [10, 20]})
    )
    assert len(zs) == 2
    assert zs.ids == ["a", "b"]
    assert zs.attribute("households").sum() == 30
    with pytest.raises(KeyError):
        zs.attribute("missing")


def test_zone_system_rejects_duplicate_ids():
    import pandas as pd

    with pytest.raises(ValueError, match="unique"):
        ZoneSystem.from_frame(pd.DataFrame({"zone_id": ["a", "a"]}))
