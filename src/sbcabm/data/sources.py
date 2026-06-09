"""Declarative registry of public data sources.

Keeping every external dataset described in one place — its host, URL template,
geography, vintage knob and license — makes ingestion auditable and keeps URLs
out of the business logic. Add a dataset here, then write its loader.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataSource:
    key: str
    name: str
    host: str
    url_template: str
    geography: str
    license: str
    notes: str = ""

    def url(self, **params: object) -> str:
        """Render the URL template with the given parameters."""
        return self.url_template.format(**params)


SOURCES: dict[str, DataSource] = {
    "acs5": DataSource(
        key="acs5",
        name="ACS 5-year detailed tables",
        host="api.census.gov",
        url_template="https://api.census.gov/data/{year}/acs/acs5",
        geography="block group / tract",
        license="public domain (US Government work)",
        notes="Marginal control totals for population synthesis.",
    ),
    "pums": DataSource(
        key="pums",
        name="ACS PUMS (Public Use Microdata Sample)",
        host="api.census.gov",
        url_template="https://api.census.gov/data/{year}/acs/acs5/pums",
        geography="PUMA",
        license="public domain (US Government work)",
        notes="Seed households and persons for synthesis.",
    ),
    "tiger_bg": DataSource(
        key="tiger_bg",
        name="TIGER/Line block groups",
        host="www2.census.gov",
        url_template=(
            "https://www2.census.gov/geo/tiger/TIGER{year}/BG/"
            "tl_{year}_{state_fips}_bg.zip"
        ),
        geography="block group",
        license="public domain (US Government work)",
        notes="Zone geometries and centroids.",
    ),
    "tiger_puma": DataSource(
        key="tiger_puma",
        name="TIGER/Line PUMAs",
        host="www2.census.gov",
        url_template=(
            "https://www2.census.gov/geo/tiger/TIGER{year}/PUMA/"
            "tl_{year}_{state_fips}_puma{yy}.zip"
        ),
        geography="PUMA",
        license="public domain (US Government work)",
        notes="Resolve which PUMAs cover the county; link PUMS to geography.",
    ),
    "lodes_wac": DataSource(
        key="lodes_wac",
        name="LEHD LODES Workplace Area Characteristics",
        host="lehd.ces.census.gov",
        url_template=(
            "https://lehd.ces.census.gov/data/lodes/LODES8/{state}/wac/"
            "{state}_wac_S000_JT00_{year}.csv.gz"
        ),
        geography="block",
        license="public domain (US Government work)",
        notes="Employment by sector → zonal size terms.",
    ),
    "gazetteer_bg": DataSource(
        key="gazetteer_bg",
        name="Census Gazetteer — block groups",
        host="www2.census.gov",
        url_template=(
            "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
            "{year}_Gazetteer/{year}_gaz_blockgroups_{state_fips}.txt"
        ),
        geography="block group",
        license="public domain (US Government work)",
        notes="Tab-delimited block-group centroids (INTPTLAT/LONG) and land area.",
    ),
    "osm": DataSource(
        key="osm",
        name="OpenStreetMap (Geofabrik California extract)",
        host="download.geofabrik.de",
        url_template="https://download.geofabrik.de/north-america/us/california-latest.osm.pbf",
        geography="state extract (clip to county)",
        license="ODbL © OpenStreetMap contributors",
        notes="Routable highway / bike / walk network.",
    ),
    "gtfs_sbmtd": DataSource(
        key="gtfs_sbmtd",
        name="GTFS — Santa Barbara MTD",
        host="api.sbmtd.gov",
        url_template="https://www.sbmtd.gov/google_transit/google_transit.zip",
        geography="county",
        license="published by SBMTD",
        notes="Local fixed-route transit schedules.",
    ),
}


def get_source(key: str) -> DataSource:
    if key not in SOURCES:
        raise KeyError(f"unknown data source '{key}'; known: {sorted(SOURCES)}")
    return SOURCES[key]
