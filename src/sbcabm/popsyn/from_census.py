"""Build population-synthesis inputs from ingested Census tables.

Turns the raw ingest outputs — an ACS block-group table and PUMS household /
person records — into the four tables the synthesizer consumes:
``seed_households``, ``seed_persons``, ``incidence`` and ``controls``.
"""

from __future__ import annotations

import logging

import pandas as pd

from .marginals import build_controls
from .seed import apply_recodes, build_seed_incidence
from .specs import (
    ControlSpec,
    Recode,
    all_control_specs,
    default_recodes,
)

logger = logging.getLogger("sbcabm.popsyn.from_census")

SEED_HH_ID = "seed_household_id"


def build_popsyn_inputs(
    acs_block_groups: pd.DataFrame,
    pums_households: pd.DataFrame,
    pums_persons: pd.DataFrame,
    *,
    specs: tuple[ControlSpec, ...] | None = None,
    recodes: tuple[Recode, ...] | None = None,
    geoid_col: str = "GEOID",
    serialno_col: str = "SERIALNO",
) -> dict[str, pd.DataFrame]:
    """Assemble synthesizer inputs from ingested Census tables.

    Returns a dict with ``seed_households`` and ``incidence`` indexed by
    ``seed_household_id``, ``seed_persons`` carrying that id column, and
    ``controls`` indexed by ``zone_id``.
    """
    specs = specs or all_control_specs()
    recodes = recodes or default_recodes()

    controls = build_controls(acs_block_groups, specs, geoid_col=geoid_col)

    # Household-level recodes (size, income) operate on one row per household.
    hh = pums_households.drop_duplicates(serialno_col).set_index(serialno_col)
    hh.index.name = SEED_HH_ID
    hh_recodes = tuple(r for r in recodes if r.source in hh.columns)
    seed_households = apply_recodes(hh, hh_recodes)

    # Person-level recodes (age) operate on the person records, linked by SERIALNO.
    persons = pums_persons.copy()
    if serialno_col not in persons.columns:
        raise KeyError(f"pums_persons is missing '{serialno_col}'")
    person_recodes = tuple(r for r in recodes if r.source in persons.columns)
    seed_persons = apply_recodes(persons, person_recodes)
    seed_persons[SEED_HH_ID] = seed_persons[serialno_col]

    incidence = build_seed_incidence(
        seed_households, seed_persons, specs, hh_id_col=SEED_HH_ID
    )

    logger.info(
        "built popsyn inputs: %d seed households, %d seed persons, %d zones, %d controls",
        len(seed_households),
        len(seed_persons),
        len(controls),
        incidence.shape[1],
    )
    return {
        "seed_households": seed_households,
        "seed_persons": seed_persons,
        "incidence": incidence,
        "controls": controls,
    }
