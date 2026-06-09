# Public data sources

Every input needed to stand up a baseline SBC ABM is publicly available and free.
Raw downloads are **not** committed to the repo (see `.gitignore`); they are
fetched into `data/cache/` by the ingestion layer and documented here for
provenance. Santa Barbara County FIPS = **06083** (state 06, county 083).

| Dataset | Source | Used for | Geography | Module |
|---|---|---|---|---|
| ACS 5-year detailed tables | Census Bureau API | Marginal control totals (households by size/income, persons by age/sex) | Block group / tract | `data/census.py` |
| PUMS (Public Use Microdata Sample) | Census Bureau API / FTP | Seed households & persons for synthesis | PUMA | `data/census.py` |
| Census Gazetteer | Census Bureau | Zone centroids (INTPTLAT/LONG) + land area | Block group | `data/geographies.py` |
| LODES / LEHD (WAC) | Census LEHD | Employment by sector per zone (size terms) | Block → block group | `data/employment.py` |
| TIGER/Line shapefiles | Census Bureau | Polygon geometry, centroids, adjacency | Block group, tract, PUMA | `data/tiger.py` *(geo extra)* |
| OpenStreetMap | Geofabrik / Overpass | Routable highway, bike, walk networks | County | `data/networks.py` *(planned)* |
| GTFS — SBMTD | Santa Barbara MTD | Local transit routes, stops, schedules | County | `data/transit.py` *(planned)* |
| GTFS — Clean Air Express / Amtrak | respective agencies | Regional/commuter transit | Region | `data/transit.py` *(planned)* |
| NHTS / CHTS | FHWA / Caltrans | Activity & tour rate targets, mode-choice calibration | National/state | calibration *(planned)* |

## Geographic scope

- **State FIPS:** 06 (California)
- **County FIPS:** 083 (Santa Barbara)
- **PUMAs:** Santa Barbara County is covered by several PUMAs; the exact set is
  resolved at ingestion time from the TIGER PUMA layer.
- **Default model zones:** Census **block groups** within the county, used as
  TAZs until/unless a custom TAZ layer is provided.

## Vintages

The default ACS/PUMS vintage and TIGER year are set in `configs/settings.yaml`
(`data.acs_year`, `data.tiger_year`). Pin these for reproducibility.

## Licensing

US Census, LEHD/LODES, and TIGER/Line are US Government works (public domain).
OpenStreetMap is © OpenStreetMap contributors, ODbL. GTFS feeds are published by
the respective transit agencies under their own terms. Keep attribution intact
in any derived, published outputs.

## Network access note

Ingestion requires outbound HTTPS to the hosts above (e.g. `api.census.gov`,
`www2.census.gov`, Geofabrik, agency GTFS URLs). In restricted environments
those hosts may be blocked; in that case the pipeline falls back to the
fixtures under `tests/fixtures/` so the model mechanics remain exercisable
offline. Run ingestion in an environment whose network policy allows these
hosts to populate `data/cache/` for a real run.
