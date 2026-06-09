"""The ``longterm`` pipeline stage: long-term and mobility choices.

Runs the choices that condition all later travel and writes them onto the
synthetic population:

* auto ownership → ``auto_ownership`` on ``households``;
* usual workplace location → ``workplace_zone`` on worker ``persons``;
* usual school location → ``school_zone`` on student ``persons``;
* transit pass holding → ``transit_pass`` on ``persons``;
* telecommute frequency → ``telecommute_freq`` on worker ``persons``.

Workers are persons of working age (18–64) and students are ages 5–18 — pragmatic
proxies until a dedicated employment/enrollment-status model exists.
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
from .mobility import run_telecommute, run_transit_pass
from .school_location import choose_school
from .work_location import choose_workplace

logger = logging.getLogger("sbcabm.longterm")

_WORK_AGE_MIN, _WORK_AGE_MAX = 18, 64
_SCHOOL_AGE_MIN, _SCHOOL_AGE_MAX = 5, 18


def run_longterm(config: Config, store: DataStore) -> None:
    for table in ("households", "persons", "zones"):
        if not store.has(table):
            raise KeyError(f"longterm stage requires '{table}'; run earlier stages first")

    rng = np.random.default_rng(config.random_seed)
    zones = store.get("zones")

    # 1) Auto ownership (household level).
    households = store.get("households").copy()
    auto_spec = load_spec(_spec(config, "auto_ownership.csv"))
    households["auto_ownership"] = run_auto_ownership(
        households, zones, auto_spec, rng=rng
    ).to_numpy()
    store.put("households", households)

    # 2) Person-level long-term choices. Enrich persons with household context.
    persons = _enrich_persons(store.get("persons").copy(), households)
    age = pd.to_numeric(persons["AGEP"], errors="coerce") if "AGEP" in persons else None
    auto_skim = store.get("skims").query("mode == 'auto'") if store.has("skims") else None
    has_employment = "emp_total" in zones.columns

    persons["workplace_zone"] = _locate(
        persons, age, _WORK_AGE_MIN, _WORK_AGE_MAX, zones, auto_skim, has_employment,
        chooser=choose_workplace, label="workplace",
    )
    persons["has_workplace"] = persons["workplace_zone"].notna()
    persons["school_zone"] = _locate(
        persons, age, _SCHOOL_AGE_MIN, _SCHOOL_AGE_MAX, zones, auto_skim, has_employment,
        chooser=choose_school, label="school",
    )

    persons["transit_pass"] = run_transit_pass(
        persons, load_spec(_spec(config, "transit_pass.csv")), rng=rng
    ).to_numpy()

    persons["telecommute_freq"] = _assign_telecommute(persons, age, config, rng)

    store.put("persons", persons)


def _enrich_persons(persons: pd.DataFrame, households: pd.DataFrame) -> pd.DataFrame:
    """Attach household auto ownership and income onto persons."""
    by_hh = households.set_index("household_id")
    for col in ("auto_ownership", "HINCP"):
        if col in by_hh.columns and col not in persons.columns:
            persons[col] = persons["household_id"].map(by_hh[col])
    if "AGEP" not in persons.columns:
        persons["AGEP"] = 0
    return persons


def _locate(
    persons, age, age_min, age_max, zones, auto_skim, has_employment, *, chooser, label
) -> pd.Series:
    """Run a destination-choice locator over the age-eligible subset."""
    result = pd.Series(index=persons.index, dtype=object)
    if age is None or auto_skim is None or not has_employment:
        logger.warning("missing inputs; skipping %s location", label)
        return result
    eligible = persons[age.between(age_min, age_max)]
    if eligible.empty:
        return result
    result.loc[eligible.index] = chooser(eligible, zones, auto_skim, rng=_chooser_rng(label))
    return result


def _chooser_rng(label: str) -> np.random.Generator:
    """A stable, per-model RNG so adding a model doesn't reshuffle the others."""
    return np.random.default_rng(abs(hash(label)) % (2**32))


def _assign_telecommute(persons, age, config, rng) -> pd.Series:
    result = pd.Series(index=persons.index, dtype=object)
    if age is None:
        return result
    workers = persons[age.between(_WORK_AGE_MIN, _WORK_AGE_MAX)]
    if workers.empty:
        return result
    spec = load_spec(_spec(config, "telecommute.csv"))
    result.loc[workers.index] = run_telecommute(workers, spec, rng=rng)
    return result


def _spec(config: Config, name: str) -> Path:
    candidate = config.config_dir / "specs" / name
    return candidate if candidate.exists() else Path("configs/specs") / name
