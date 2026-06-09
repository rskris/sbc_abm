"""The ``longterm`` pipeline stage: auto ownership and workplace location.

Runs the long-term mobility choices that condition all later travel:

* auto ownership → writes ``auto_ownership`` onto ``households``;
* workplace location → writes ``workplace_zone`` onto worker ``persons``.

Workers are taken as persons of working age (18–64) as a pragmatic proxy until a
dedicated employment-status model exists.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ..choice import load_spec
from ..config import Config
from ..pipeline import DataStore
from .auto_ownership import run_auto_ownership
from .work_location import choose_workplace

logger = logging.getLogger("sbcabm.longterm")

_AUTO_SPEC = Path("configs/specs/auto_ownership.csv")
_WORK_AGE_MIN = 18
_WORK_AGE_MAX = 64


def run_longterm(config: Config, store: DataStore) -> None:
    for table in ("households", "persons", "zones"):
        if not store.has(table):
            raise KeyError(f"longterm stage requires '{table}'; run earlier stages first")

    rng = np.random.default_rng(config.random_seed)
    households = store.get("households").copy()
    zones = store.get("zones")

    spec = load_spec(_resolve_spec(config, _AUTO_SPEC))
    households["auto_ownership"] = run_auto_ownership(households, zones, spec, rng=rng).to_numpy()
    store.put("households", households)

    persons = store.get("persons").copy()
    persons["workplace_zone"] = _assign_workplaces(persons, zones, store, rng)
    store.put("persons", persons)


def _assign_workplaces(
    persons: pd.DataFrame, zones: pd.DataFrame, store: DataStore, rng: np.random.Generator
) -> pd.Series:
    workplace = pd.Series(index=persons.index, dtype=object)

    if "AGEP" not in persons.columns:
        logger.warning("persons lack 'AGEP'; skipping workplace location")
        return workplace
    if not store.has("skims") or "emp_total" not in zones.columns:
        logger.warning("no auto skims or zone employment; skipping workplace location")
        return workplace

    age = pd.to_numeric(persons["AGEP"], errors="coerce")
    is_worker = age.between(_WORK_AGE_MIN, _WORK_AGE_MAX)
    workers = persons[is_worker]
    if workers.empty:
        return workplace

    auto_skim = store.get("skims").query("mode == 'auto'")
    chosen = choose_workplace(workers, zones, auto_skim, rng=rng)
    workplace.loc[workers.index] = chosen
    logger.info("workplace location: %d workers of %d persons", len(workers), len(persons))
    return workplace


def _resolve_spec(config: Config, relative: Path) -> Path:
    """Find a spec under the config file's directory (specs/...), else the CWD."""
    candidate = config.config_dir / "specs" / relative.name
    return candidate if candidate.exists() else relative
