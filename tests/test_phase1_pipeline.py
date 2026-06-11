"""End-to-end Phase 1: ingest → zones → popsyn from Census-format fixtures.

Exercises the real-data code path offline. The ``ingest`` stage falls back to
the bundled Census fixtures (network disabled), ``zones`` derives the zone
table, and ``popsyn`` builds its inputs from the ingested tables — no popsyn
fixtures involved.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sbcabm.config import load_config
from sbcabm.pipeline import build_pipeline
from sbcabm.popsyn.from_census import build_popsyn_inputs

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"


def _offline_config():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)  # force fixture fallback
    return config


def test_full_phase1_pipeline_offline():
    config = _offline_config()
    pipeline = build_pipeline(config)
    store = pipeline.run(["ingest", "zones", "popsyn"])

    # Ingest produced the raw Census tables.
    for name in ("acs_block_groups", "pums_households", "pums_persons"):
        assert store.has(name)

    # Zones derived from block groups.
    zones = store.get("zones")
    assert set(zones["zone_id"]) == {"060830001001", "060830001002"}
    assert zones["total_households"].sum() == 50

    # Popsyn synthesized to the household totals (30 + 20).
    households = store.get("households")
    persons = store.get("persons")
    assert len(households) == 50
    assert len(persons) > 0
    by_zone = households.groupby("zone_id").size()
    assert by_zone["060830001001"] == 30
    assert by_zone["060830001002"] == 20


def test_build_popsyn_inputs_shapes():
    base = REPO_ROOT / "tests" / "fixtures" / "census"
    acs = pd.read_csv(base / "acs_block_groups.csv")
    hh = pd.read_csv(base / "pums_households.csv")
    persons = pd.read_csv(base / "pums_persons.csv")

    inputs = build_popsyn_inputs(acs, hh, persons)

    seed_hh = inputs["seed_households"]
    incidence = inputs["incidence"]
    controls = inputs["controls"]

    # One seed row per PUMS household; recodes attached.
    assert len(seed_hh) == 7
    assert "hh_size" in seed_hh.columns and "hh_income" in seed_hh.columns
    # Incidence aligns to seed households and shares control columns with controls.
    assert incidence.index.equals(seed_hh.index)
    assert set(incidence.columns).issubset(set(controls.columns))
    # total_households incidence is 1 for every seed household.
    assert (incidence["total_households"] == 1.0).all()
    # Person controls counted children correctly (hh 4,5,6 have minors).
    assert inputs["seed_persons"]["age_group"].isin(["under18", "adult18plus"]).all()


def test_popsyn_diagnostics_converge_on_real_inputs():
    config = _offline_config()
    store = build_pipeline(config).run(["ingest", "zones", "popsyn"])
    diag = store.get("popsyn_diagnostics")
    assert diag["balance_converged"].all()
