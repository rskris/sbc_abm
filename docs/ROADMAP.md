# Roadmap

A staged plan to grow SBC ABM from the current foundation to a full,
production-usable model. Each phase produces something runnable and testable.

Legend: ✅ done · 🚧 in progress · ⬜ planned

## Phase 0 — Foundation ✅
- ✅ Repo scaffolding, packaging (`pyproject.toml`), CI, tests, docs.
- ✅ Typed, validated YAML configuration (`config.py`).
- ✅ Stage-based pipeline orchestrator with a checkpointed data store.
- ✅ Public-data source registry (`data/sources.py`).
- ✅ Census ACS/PUMS ingestion client with caching (`data/census.py`).
- ✅ **Population synthesis core**: IPF, list-balancing/IPU, integerizer,
  synthesizer (`popsyn/`), with unit tests.

## Phase 1 — Zones & inputs 🚧
- ✅ `ingest` stage: ACS marginals + PUMS seed records via the Census client,
  with a fixture fallback for offline runs.
- ✅ Spec-driven controls: ACS detailed-table variables → per-zone marginals
  (`marginals.py`); PUMS recodes → seed incidence (`seed.py`); default SB County
  scheme (`specs.py`, draft — verify variable IDs against the live API).
- ✅ `zones` stage: model zone table (block groups as TAZs) from ingested data.
- ✅ Popsyn consumes ingested Census tables end-to-end (`from_census.py`);
  infeasible controls (sparse-seed categories) are relaxed, not fatal.
- ✅ LODES (LEHD) WAC employment aggregated block→block-group into model
  categories (retail/office/industrial/education/health/service size terms).
- ✅ Zone centroids + land area from Census Gazetteer (no geopandas needed);
  zone table enriched with employment, centroids, and densities.
- ✅ TIGER/Line polygon geometry (geo extra): standardized zone polygons,
  geometric centroids/area, and a zone adjacency (contiguity) edge list.
- ⬜ Run against live SB County data in a network-enabled environment; validate
  the default ACS/PUMS variable scheme for the configured vintage.

**Phase 1 is functionally complete** — the data foundation (synthetic
population + a zone system with land use, employment, geometry and adjacency) is
in place. Remaining items are live-data validation.

## Phase 2 — Networks & skims ✅
- ✅ Multimodal `Network` over tidy `network_nodes`/`network_links` tables
  (`networkx`); mode-filtered graphs with per-link or constant-speed times.
- ✅ OSM → network tables (`network/build.py`, best-effort, lazy `osmnx`) with a
  fixture fallback; `network` pipeline stage.
- ✅ Centroid connectors tying zones to the network.
- ✅ Free-flow **skims** (auto/walk/bike) by shortest path, long-form by mode and
  time period; `skims` pipeline stage.
- ✅ GTFS ingestion (`data/transit.py`) → stops/routes/trips/stop_times.
- ✅ Schedule-based **transit skims** via RAPTOR (`skims/transit.py`): timetable
  build, round-based earliest-arrival routing, and zone-to-zone skims decomposed
  into access / in-vehicle / wait / transfer-walk / egress + transfer count;
  `transit_skims` pipeline stage.
- ⬜ Time-of-day periods with congested speeds (closes the loop with assignment,
  Phase 6).

## Phase 3 — Long-term & mobility choices ⬜
- ⬜ Auto-ownership model (ordered/multinomial logit).
- ⬜ Usual workplace & school location choice (destination-choice logit, size
  terms from employment/enrollment).
- ⬜ Transit pass / telecommute frequency.

## Phase 4 — Daily activities & tours ⬜
- ⬜ Coordinated Daily Activity Pattern (CDAP): mandatory / non-mandatory / home.
- ⬜ Tour frequency (mandatory, then non-mandatory).
- ⬜ Tour time-of-day scheduling.
- ⬜ Tour primary-destination choice.

## Phase 5 — Mode & trips ⬜
- ⬜ Tour mode choice (nested logit: auto/transit/active sub-nests).
- ⬜ Intermediate-stop frequency & location.
- ⬜ Trip departure time & trip mode choice → final **trip list / agent plans**.

## Phase 6 — Assignment & equilibrium ⬜
- ⬜ Static volume-delay (BPR) assignment for fast iterations.
- ⬜ MATSim-style dynamic mobsim with per-agent scoring + co-evolutionary
  re-planning.
- ⬜ Demand↔supply feedback loop to skim equilibrium; convergence diagnostics.

## Phase 7 — Calibration, validation, reporting ⬜
- ⬜ Calibrate to NHTS/CHTS targets and SBCAG validation data.
- ⬜ Standard measures: VMT, mode share, transit ridership, accessibility, equity.
- ⬜ Scenario tooling (land use, pricing, transit service) + reporting notebooks.

## Cross-cutting
- ⬜ Performance: vectorized choice evaluation, chunking, optional Polars/Arrow.
- ⬜ Validation gates in CI as each model is calibrated.
- ⬜ Reproducible run manifests (config + data hashes + seed).
