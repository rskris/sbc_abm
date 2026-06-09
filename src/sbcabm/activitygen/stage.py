"""The ``activitygen`` pipeline stage.

Runs the daily activity / tour generation sequence and writes:

* ``daily_pattern`` onto ``persons`` (CDAP), and
* a ``tours`` table with purpose, primary destination, and time of day.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ..choice import load_spec
from ..config import Config
from ..pipeline import DataStore
from .cdap import run_cdap
from .scheduling import schedule_tours
from .tours import assign_destinations, generate_tours, run_nonmandatory_frequency

logger = logging.getLogger("sbcabm.activitygen")

_CDAP_SPEC = "cdap.csv"
_NM_FREQ_SPEC = "nonmandatory_tour_frequency.csv"


def run_activitygen(config: Config, store: DataStore) -> None:
    for table in ("households", "persons", "zones"):
        if not store.has(table):
            raise KeyError(f"activitygen requires '{table}'; run earlier stages first")

    rng = np.random.default_rng(config.random_seed)
    households = store.get("households")
    zones = store.get("zones")
    persons = _prepare_persons(store.get("persons"), households)

    cdap_spec = load_spec(_spec_path(config, _CDAP_SPEC))
    persons["daily_pattern"] = run_cdap(persons, cdap_spec, rng=rng).to_numpy()

    nm_spec = load_spec(_spec_path(config, _NM_FREQ_SPEC))
    nm_counts = run_nonmandatory_frequency(persons, nm_spec, rng=rng)

    tours = generate_tours(persons, nm_counts, rng=rng)
    if store.has("skims"):
        auto_skim = store.get("skims").query("mode == 'auto'")
        tours = assign_destinations(tours, persons, zones, auto_skim, rng=rng)
    else:
        logger.warning("no auto skims; tours default to their home zone")
        tours["dest_zone"] = tours["home_zone"]
    tours = schedule_tours(tours, rng=rng)

    store.put("persons", persons)
    store.put("tours", tours)
    logger.info(
        "activitygen: %d persons patterned, %d tours generated", len(persons), len(tours)
    )


def _prepare_persons(persons: pd.DataFrame, households: pd.DataFrame) -> pd.DataFrame:
    """Attach household auto ownership; ensure the columns the models need exist."""
    persons = persons.copy()
    if "auto_ownership" in households.columns and "auto_ownership" not in persons.columns:
        owner = households.set_index("household_id")["auto_ownership"]
        persons["auto_ownership"] = persons["household_id"].map(owner)
    if "auto_ownership" not in persons.columns:
        persons["auto_ownership"] = "cars_1"
    persons["auto_ownership"] = persons["auto_ownership"].fillna("cars_0")
    return persons


def _spec_path(config: Config, name: str) -> Path:
    candidate = config.config_dir / "specs" / name
    return candidate if candidate.exists() else Path("configs/specs") / name
