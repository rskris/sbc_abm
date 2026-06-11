# Product Requirements Document — SBC ABM

**Status:** Approved · **Version:** 1.0 · **PM pass:** 2026-06
Derived from [`project-brief.md`](project-brief.md).

## Goals

1. Produce a defensible, person-level travel demand simulation for Santa
   Barbara County from public data alone.
2. Keep every behavioral parameter editable as data, not code.
3. Make the system testable offline, end-to-end, in CI.
4. Close the demand↔supply loop (congestion feedback) and support calibration.

## Functional requirements

| ID | Requirement | Epic |
|---|---|---|
| FR1 | Ingest ACS marginals, PUMS seed records, LODES employment, Gazetteer centroids/area, and TIGER polygons for the county, with on-disk caching and fixture fallback. | 1 |
| FR2 | Build a zone system (block groups as TAZs) carrying households, employment by sector, centroids, area, densities, geometry, and adjacency. | 1 |
| FR3 | Synthesize a household/person population matching zonal marginal controls (IPF/IPU + integerization), with per-zone convergence diagnostics. | 1 |
| FR4 | Build a routable multimodal network (OSM or tables), centroid connectors, and free-flow auto/walk/bike skims. | 2 |
| FR5 | Ingest GTFS and produce schedule-based transit skims (RAPTOR) decomposed into access/IVT/wait/transfer/egress + transfers. | 2 |
| FR6 | Provide a reusable discrete-choice engine: CSV utility specs, MNL, nested logit, destination choice with optional alternative sampling, seeded simulation. | 3 |
| FR7 | Simulate long-term choices: auto ownership, usual workplace & school location, transit pass, telecommute frequency. | 3 |
| FR8 | Simulate daily patterns: household-interaction CDAP, tour frequency, joint household tours, tour destinations, discrete time-of-day. | 4 |
| FR9 | Simulate tour & trip mode choice (nested: auto/transit/active) with availability rules, joint half-tour stop frequency/purpose, and emit a complete trip list. | 5 |
| FR10 | Load trips onto the network (static BPR first; MATSim-style mobsim later), produce link volumes and congested times, and feed skims back to demand until equilibrium. | 6 |
| FR11 | Compute standard measures (VMT, mode shares, transit boardings, accessibility) and support calibration against observed targets. | 7 |
| FR12 | Expose the whole pipeline via a CLI (`sbcabm info/run`) driven by one YAML config. | 0 |

## Non-functional requirements

| ID | Requirement |
|---|---|
| NFR1 | **Reproducibility:** identical (config, data, seed) ⇒ identical outputs; one `random_seed` governs all draws. |
| NFR2 | **Offline testability:** every stage runs against bundled fixtures with no network; CI never needs external APIs. |
| NFR3 | **Config-as-data:** utility coefficients, control schemes, and nests live in `configs/`, never in code. |
| NFR4 | **Dependency tiers:** core = numpy/pandas/scipy/networkx/pyyaml/requests; geopandas and osmnx isolated behind `geo`/`osm` extras with lazy imports. |
| NFR5 | **Quality gates:** ruff clean and pytest green on Python 3.10/3.11/3.12 in CI for every commit. |
| NFR6 | **Performance:** county-scale full run (~450k persons) on a single machine; vectorized choice evaluation; per-origin probability sharing. |
| NFR7 | **Graceful degradation:** optional inputs (LODES, Gazetteer, TIGER, GTFS) failing must not abort a run; capabilities shrink with a logged warning. |
| NFR8 | **Licensing:** MIT code; public-domain or ODbL data with attribution preserved. |

## Epic list

| Epic | Title | Status |
|---|---|---|
| 0 | Foundation: packaging, config, pipeline orchestrator, CLI, CI | **Done** |
| 1 | Data foundation: ingestion, zones, population synthesis | **Done** |
| 2 | Networks & skims: multimodal graph, road skims, RAPTOR transit | **Done** |
| 3 | Long-term & mobility choices + discrete-choice engine | **Done** |
| 4 | Daily activities & tours | **Done** |
| 5 | Mode & trips | **Done** |
| 6 | Assignment & equilibrium | **Done** |
| 7 | Calibration, validation & reporting | **Done** (7.5 blocked on OD2) |

Epic details and stories: [`epics/`](epics/).

## Product decisions

- **OD1 — Validation targets: RESOLVED (2026-06).** Primary: **ACS county
  data** (B08301 commute mode shares, B08201 household vehicles) — same public
  API the model ingests from, county-specific, fetched automatically during
  ingest and turned into targets by `measures/targets.py`. Secondary:
  **NHTS 2017 published rates** curated in
  `configs/validation/nhts2017_targets.csv` (replace with CA add-on values
  when extracted). Rejected: CHTS (2010–12 vintage, restricted access) and
  SBCAG counts (no public feed; deferred to link-level validation under a
  data-sharing agreement).
- **OD2 — Live-run environment: pending owner action.** All code is ready
  (preflight, strict mode, runbook, `configs/live.yaml`); the environment's
  network policy must allow the five public-data hosts, then story 7.5
  executes in a fresh session.
