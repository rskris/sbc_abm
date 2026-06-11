"""The ``ingest`` pipeline stage: fetch public inputs into the data store.

Fetches the inputs population synthesis and the zone system need:

* ACS block-group marginals and PUMS seed records (via the cached Census API
  client), and
* LODES workplace employment and Census Gazetteer centroids/area (flat-file
  downloads), which enrich the zone system.

ACS/PUMS are required; LODES and the Gazetteer are best-effort (a model can run
without employment/centroids, just with fewer downstream attributes). When the
network is unavailable or a query fails, the whole stage falls back to the
bundled Census-format fixtures so the pipeline still runs offline.

Outputs (when available): ``acs_block_groups``, ``pums_households``,
``pums_persons``, ``lodes_wac``, ``gazetteer``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests

from ..config import Config
from ..pipeline import DataStore
from ..popsyn.specs import (
    PUMS_HOUSEHOLD_VARIABLES,
    PUMS_PERSON_VARIABLES,
    acs_variables,
    all_control_specs,
)
from .census import CensusClient
from .sources import get_source
from .tiger import (
    clip_to_county,
    geodataframe_from_wkt,
    read_block_group_shapefile,
    standardize_geometries,
)

logger = logging.getLogger("sbcabm.data.ingest")

_REQUIRED_OUTPUTS = ("acs_block_groups", "pums_households", "pums_persons")
_OPTIONAL_OUTPUTS = ("lodes_wac", "gazetteer", "block_group_geometries")
_SERIALNO = "SERIALNO"
_DOWNLOAD_TIMEOUT = 60


def run_ingest(config: Config, store: DataStore) -> None:
    specs = all_control_specs()
    try:
        _ingest_from_census(config, store, specs)
    except Exception as exc:  # noqa: BLE001 — any failure → documented fixture fallback
        if config.data.strict:
            raise RuntimeError(
                "census ingest failed and data.strict is set (live run); "
                f"refusing fixture fallback: {exc}"
            ) from exc
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

    # Best-effort enrichment sources: a failure here is non-fatal.
    _try_optional(store, "lodes_wac", lambda: _fetch_lodes(config))
    _try_optional(store, "gazetteer", lambda: _fetch_gazetteer(config))
    _try_optional(store, "block_group_geometries", lambda: _fetch_tiger(config))


def _split_pums(pums: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split combined PUMS person records into household and person tables."""
    hh_cols = [c for c in PUMS_HOUSEHOLD_VARIABLES if c in pums.columns]
    households = pums[hh_cols].drop_duplicates(_SERIALNO).reset_index(drop=True)
    person_cols = [c for c in PUMS_PERSON_VARIABLES if c in pums.columns]
    persons = pums[person_cols].reset_index(drop=True)
    return households, persons


def _try_optional(store: DataStore, name: str, fetch) -> None:
    try:
        store.put(name, fetch())
    except Exception as exc:  # noqa: BLE001 — optional inputs degrade gracefully
        logger.warning("optional input '%s' unavailable (%s); skipping", name, exc)


def _fetch_lodes(config: Config) -> pd.DataFrame:
    source = get_source("lodes_wac")
    state = config.region.state_fips
    state_abbr = _STATE_ABBR.get(state, state).lower()
    url = source.url(state=state_abbr, year=config.data.acs_year)
    cache = Path(config.paths.cache_dir) / "lodes" / Path(url).name
    return _download_table(url, cache, allow_network=config.data.allow_network)


def _fetch_gazetteer(config: Config) -> pd.DataFrame:
    source = get_source("gazetteer_bg")
    url = source.url(year=config.data.tiger_year, state_fips=config.region.state_fips)
    cache = Path(config.paths.cache_dir) / "gazetteer" / Path(url).name
    # Gazetteer files are tab-delimited, latin-1 encoded.
    return _download_table(
        url, cache, allow_network=config.data.allow_network, sep="\t", encoding="latin-1"
    )


def _fetch_tiger(config: Config):
    """Download and clip TIGER/Line block-group polygons for the county."""
    source = get_source("tiger_bg")
    url = source.url(year=config.data.tiger_year, state_fips=config.region.state_fips)
    cache = Path(config.paths.cache_dir) / "tiger" / Path(url).name
    if not cache.exists():
        if not config.data.allow_network:
            raise RuntimeError(f"network disabled and no cache at {cache}")
        cache.parent.mkdir(parents=True, exist_ok=True)
        logger.info("downloading %s", url)
        response = requests.get(url, timeout=_DOWNLOAD_TIMEOUT)
        response.raise_for_status()
        cache.write_bytes(response.content)
    gdf = read_block_group_shapefile(str(cache))
    gdf = clip_to_county(gdf, config.region.county_geoid)
    return standardize_geometries(gdf)


def _download_table(url: str, cache: Path, *, allow_network: bool, **read_kwargs) -> pd.DataFrame:
    if not cache.exists():
        if not allow_network:
            raise RuntimeError(f"network disabled and no cache at {cache}")
        cache.parent.mkdir(parents=True, exist_ok=True)
        logger.info("downloading %s", url)
        response = requests.get(url, timeout=_DOWNLOAD_TIMEOUT)
        response.raise_for_status()
        cache.write_bytes(response.content)
    return pd.read_csv(cache, dtype={"GEOID": str, "w_geocode": str}, **read_kwargs)


def _ingest_from_fixtures(config: Config, store: DataStore) -> None:
    fixtures = Path(config.paths.fixtures_dir) / "census"
    # Identifier columns must stay strings: a 12-digit block-group GEOID, a
    # 15-digit block w_geocode, or a PUMS SERIALNO would otherwise lose leading
    # zeros when parsed as integers.
    id_dtypes = {"GEOID": str, "SERIALNO": str, "w_geocode": str}
    for name in (*_REQUIRED_OUTPUTS, *_OPTIONAL_OUTPUTS):
        path = fixtures / f"{name}.csv"
        if not path.exists():
            if name in _OPTIONAL_OUTPUTS:
                continue
            raise FileNotFoundError(
                f"census fixture '{name}' not found at {path}; cannot ingest offline"
            )
        header = pd.read_csv(path, nrows=0).columns
        dtypes = {c: t for c, t in id_dtypes.items() if c in header}
        table = pd.read_csv(path, dtype=dtypes)
        # Geometry travels as WKT in the fixture; reconstitute a GeoDataFrame
        # and standardize it just like the live TIGER path (GEOID → zone_id).
        if name == "block_group_geometries":
            table = standardize_geometries(geodataframe_from_wkt(table))
        store.put(name, table)
    logger.info("loaded census fixtures from %s", fixtures)


# Minimal state FIPS → USPS abbreviation map (extend as needed). LODES paths use
# the lowercase state abbreviation.
_STATE_ABBR = {"06": "ca"}
