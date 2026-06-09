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

## Phase 1 — Zones & inputs ⬜
- ⬜ TIGER/Line ingestion → block-group geographies, PUMAs, centroids.
- ⬜ `ZoneSystem`: default TAZs = Census block groups; land-use attributes.
- ⬜ LODES (LEHD) employment by sector to each zone.
- ⬜ Zone-level marginal controls assembled from ACS for popsyn.
- ⬜ Wire popsyn to real SB County data end-to-end (online environment).

## Phase 2 — Networks & skims ⬜
- ⬜ OSM → routable highway/bike/walk graph for the county (`osmnx`/`networkx`).
- ⬜ GTFS ingestion (SBMTD, Clean Air Express, Amtrak) → transit routes/stops.
- ⬜ Build initial **skims** (free-flow auto, transit, walk, bike) by time period.

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
