"""The ``ingest`` pipeline stage: fetch public inputs into the data store.

Fetches the ACS block-group marginals and PUMS seed records needed by
population synthesis via :class:`~sbcabm.data.census.CensusClient` (which caches
to disk). When the network is unavailable or a query fails, it falls back to the
bundled Census-format fixtures so the pipeline still runs offline.

Outputs three tables: ``acs_block_groups``, ``pums_households``, ``pums_persons``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ..config import Config
from ..pipeline import DataStore
from ..popsyn.specs import (
    PUMS_HOUSEHOLD_VARIABLES,
    PUMS_PERSON_VARIABLES,
    acs_variables,
    all_control_specs,
)
from .census import CensusClient

logger = logging.getLogger("sbcabm.data.ingest")

_OUTPUTS = ("acs_block_groups", "pums_households", "pums_persons")
_SERIALNO = "SERIALNO"


def run_ingest(config: Config, store: DataStore) -> None:
    specs = all_control_specs()
    try:
        _ingest_from_census(config, store, specs)
    except Exception as exc:  # noqa: BLE001 — any failure → documented fixture fallback
        logger.warning("census ingest unavailable (%s); loading fixtures", exc)
        _ingest_from_fixtures(config, store)


def _ingest_from_census(config: Config, store: DataStore, specs) -> None:
    client = CensusClient(
        year=config.data.acs_year,
        api_key=config.data.census_api_key,
        cache_dir=config.paths.cache_dir,
        allow_network=config.data.allow_network,
    )

    acs = client.block_group_acs(
        acs_variables(specs),
        state_fips=config.region.state_fips,
        county_fips=config.region.county_fips,
    )

    pums_vars = list(dict.fromkeys((*PUMS_HOUSEHOLD_VARIABLES, *PUMS_PERSON_VARIABLES)))
    pums = client.fetch_pums(pums_vars, state_fips=config.region.state_fips)

    households, persons = _split_pums(pums)
    store.put("acs_block_groups", acs)
    store.put("pums_households", households)
    store.put("pums_persons", persons)
    logger.info(
        "ingested ACS (%d block groups) + PUMS (%d households, %d persons)",
        len(acs),
        len(households),
        len(persons),
    )


def _split_pums(pums: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split combined PUMS person records into household and person tables."""
    hh_cols = [c for c in PUMS_HOUSEHOLD_VARIABLES if c in pums.columns]
    households = pums[hh_cols].drop_duplicates(_SERIALNO).reset_index(drop=True)
    person_cols = [c for c in PUMS_PERSON_VARIABLES if c in pums.columns]
    persons = pums[person_cols].reset_index(drop=True)
    return households, persons


def _ingest_from_fixtures(config: Config, store: DataStore) -> None:
    fixtures = Path(config.paths.fixtures_dir) / "census"
    # Identifier columns must stay strings: a 12-digit block-group GEOID or a
    # PUMS SERIALNO would otherwise lose leading zeros when parsed as integers.
    id_dtypes = {"GEOID": str, "SERIALNO": str}
    for name in _OUTPUTS:
        path = fixtures / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"census fixture '{name}' not found at {path}; cannot ingest offline"
            )
        header = pd.read_csv(path, nrows=0).columns
        dtypes = {c: t for c, t in id_dtypes.items() if c in header}
        store.put(name, pd.read_csv(path, dtype=dtypes))
    logger.info("loaded census fixtures from %s", fixtures)
