"""Shared test fixtures and path helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def popsyn_inputs() -> dict[str, pd.DataFrame]:
    base = FIXTURES / "popsyn"
    seed_households = pd.read_csv(base / "seed_households.csv").set_index(
        "seed_household_id"
    )
    incidence = pd.read_csv(base / "incidence.csv").set_index("seed_household_id")
    seed_persons = pd.read_csv(base / "seed_persons.csv")
    controls = pd.read_csv(base / "controls.csv").set_index("zone_id")
    return {
        "seed_households": seed_households,
        "seed_persons": seed_persons,
        "incidence": incidence,
        "controls": controls,
    }
