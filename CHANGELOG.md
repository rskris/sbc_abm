# Changelog

All notable changes to SBC ABM are documented here. The project follows the
**BMAD-Method** (see [`docs/bmad/`](docs/bmad/README.md)); each entry maps to an
epic or story.

## [0.1.0] — 2026-06

First feature-complete release of the framework: the entire ActivitySim-style
demand + MATSim-style supply pipeline runs end-to-end from public data, fully
tested offline (199 tests, ruff clean, CI on Python 3.10/3.11/3.12).

### Added — Epic 0: Foundation
- Packaging, typed YAML configuration, stage-based pipeline orchestrator with a
  shared data store, `sbcabm` CLI (`info` / `run` / `preflight`), GitHub Actions CI.

### Added — Epic 1: Data foundation
- Cached Census ACS/PUMS ingestion; LODES employment; Gazetteer centroids/area;
  TIGER block-group polygons + queen-contiguity adjacency.
- Population synthesis: N-dimensional IPF, IPU list balancing, largest-remainder
  integerization, synthesizer with per-zone convergence diagnostics.

### Added — Epic 2: Networks & skims
- Multimodal network (OSM or tables), centroid connectors, free-flow
  auto/walk/bike skims; GTFS ingestion; RAPTOR schedule-based transit skims with
  access/IVT/wait/transfer/egress decomposition.

### Added — Epic 3: Discrete-choice engine & long-term choices
- Reusable engine: CSV utility specs, MNL, nested logit, destination choice with
  optional alternative sampling, seeded simulation.
- Auto ownership; usual workplace & school location; transit pass; telecommute.

### Added — Epic 4: Daily activities & tours
- Household-interaction CDAP; tour frequency; fully-joint household tours; tour
  primary-destination choice; discrete time-of-day choice.

### Added — Epic 5: Mode & trips
- Tour & trip mode choice (nested logit, availability rules); joint half-tour
  stop frequency & purpose; full trip list.

### Added — Epic 6: Assignment & equilibrium
- Static BPR assignment (MSA); congested skims + demand↔supply equilibrium loop;
  Charypar–Nagel agent plans & scoring; MATSim-style co-evolutionary replanning;
  per-period network summaries (VMT/VHT/speed/congestion).

### Added — Epic 7: Calibration, validation & reporting
- Standard measures (tidy long form); validation gap report; damped ASC
  calibration harness; scenario comparison.
- Live-run tooling: `sbcabm preflight` (host reachability + live variable-scheme
  verification), `data.strict` mode, `configs/live.yaml`, runbook.

### Decisions
- **OD1 resolved:** validation targets = county ACS (commute modes, vehicles),
  auto-built during ingest, plus curated NHTS 2017 rate targets.

### Known limitations
- Model coefficients are documented defaults, **not yet calibrated** to observed
  data (harness ready; pending a live run).
- Live data run pending a network-enabled environment (**OD2**).
- v1 scope: auto-only network assignment; school location via employment proxy;
  no freight/external travel.
