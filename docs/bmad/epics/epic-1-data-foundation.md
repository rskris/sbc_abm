# Epic 1 — Data foundation: ingestion, zones, population synthesis

**Status: Done** · Delivers FR1–FR3.
Goal: from public data to a synthetic population on an attributed zone system.

## Stories

### 1.1 Population-synthesis numerics — Done
N-dimensional IPF (Deming–Stephan); IPU list balancer (Ye et al.) with
infeasible-control relaxation; largest-remainder integerizer robust to any
remainder; synthesizer expanding seed households/persons per zone with unique ids.
*Evidence:* `src/sbcabm/popsyn/{ipf,balancer,integerize,synthesizer}.py`;
`tests/test_{ipf,balancer,integerize,synthesizer}.py`.

### 1.2 Census ingestion with cache & fixtures — Done
Cached ACS/PUMS API client; declarative source registry; `ingest` stage with
offline fixture fallback; identifier columns kept as strings.
*Evidence:* `src/sbcabm/data/{census,sources,ingest}.py`; `tests/test_phase1_pipeline.py`.

### 1.3 Spec-driven controls & seed — Done
`ControlSpec`/`Recode` scheme (B11016 size, B19001 income, B01001 age) turning
ACS into per-zone marginals and PUMS into recoded seed + incidence; draft scheme
flagged for live-API validation.
*Evidence:* `src/sbcabm/popsyn/{specs,marginals,seed,from_census}.py`;
`tests/test_marginals_seed.py`.

### 1.4 Zone enrichment: employment & geography — Done
LODES WAC block→block-group aggregation into six size-term categories;
Gazetteer centroids/area; densities; graceful degradation without optional
inputs.
*Evidence:* `src/sbcabm/data/{employment,geographies}.py`,
`src/sbcabm/zones/stage.py`; `tests/test_zones_enrichment.py`.

### 1.5 TIGER polygons & adjacency — Done
TIGER block-group polygons (lazy `geo` extra), county clip, projected
centroid/area, queen-contiguity adjacency; WKT-CSV fixtures.
*Evidence:* `src/sbcabm/data/tiger.py`; `tests/test_tiger.py`.

## Carry-forward

- Validate the default ACS/PUMS variable scheme against the live API for the
  configured vintage (needs a network-enabled environment) → tracked as OD2 in
  the PRD.
