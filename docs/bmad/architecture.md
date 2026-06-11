# Architecture Document — SBC ABM (BMAD)

**Status:** Approved · **Architect pass:** 2026-06
The system design narrative lives in [`../ARCHITECTURE.md`](../ARCHITECTURE.md);
this document adds the BMAD-required engineering contracts a dev agent needs:
tech stack, source tree, coding standards, and test strategy.

## Tech stack (authoritative)

| Layer | Choice | Notes |
|---|---|---|
| Language | Python ≥ 3.10 | CI: 3.10 / 3.11 / 3.12 |
| Core libs | numpy, pandas, scipy, networkx, pyyaml, requests | always installed |
| Geospatial | geopandas, shapely, pyproj | `geo` extra, **lazy imports only** |
| OSM ingest | osmnx | `osm` extra, lazy import |
| Tests | pytest | `tests/`, fixtures under `tests/fixtures/` |
| Lint | ruff (line length 100, rules E/F/I/UP/B/W, B007 ignored) | must exit 0 |
| CI | GitHub Actions (`.github/workflows/ci.yml`) | lint + tests, 3 Pythons |
| Packaging | setuptools via `pyproject.toml`; CLI entry `sbcabm` | src layout |

## Source tree & ownership

```
configs/
  settings.yaml          # the single run config (region, seed, stages)
  specs/*.csv            # utility specs & nests — DATA, edited by PM/planner
src/sbcabm/
  config.py              # typed config loader (frozen dataclasses)
  pipeline.py            # DataStore + StageRegistry + Pipeline orchestrator
  cli.py                 # `sbcabm info|run`
  data/                  # public-data ingestion (census, lodes, gazetteer,
                         #   tiger, transit/GTFS, ingest stage, source registry)
  zones/                 # ZoneSystem + zones stage
  popsyn/                # IPF, IPU balancer, integerizer, synthesizer,
                         #   ACS→controls, PUMS→seed, popsyn stage
  network/               # Network graph, OSM build, connectors, network stage
  skims/                 # road skims, RAPTOR transit skims, stages
  choice/                # spec loader, MNL, nested logit, destination choice
  longterm/              # auto ownership, work/school location, mobility, stage
  activitygen/           # CDAP (household), tours, joint tours, TOD, stage
  modechoice/            # LOS, tour/trip mode, stops, trips, stage
  assignment/            # (Epic 6) static BPR + mobsim, feedback loop
  measures/              # (Epic 7) summaries, calibration, reporting
tests/                   # one test module per package + fixtures
docs/bmad/               # this methodology layer
```

## Stage contract (the load-bearing pattern)

Every pipeline stage is a function `run_<stage>(config: Config, store: DataStore)`
registered in `pipeline.build_default_registry()`. Stages:

1. **read** named tables from the store, raising `KeyError` with the message
   `"<stage> requires '<table>'"` when a hard prerequisite is missing;
2. **degrade gracefully** when an *optional* input is missing (log a warning,
   skip the enrichment) — never crash a run for optional data;
3. **write** named tables back; never mutate another stage's table in place
   (copy first);
4. draw randomness only from generators seeded by `config.random_seed`.

Tables currently flowing through the store (after a full run): raw ingest
(`acs_block_groups`, `pums_*`, `lodes_wac`, `gazetteer`, `block_group_geometries`),
zone layer (`zones`, `zone_geometries`, `zone_adjacency`, `zone_connectors`),
network/skims (`network_nodes`, `network_links`, `skims`, `transit_*`,
`transit_skims`), population (`households`, `persons`, `popsyn_diagnostics`),
demand (`tours`, `trips`).

## Coding standards (binding)

- Specs/coefficients in `configs/specs/*.csv`; loading via `choice.load_spec`.
- New choice models use the `choice/` engine — no bespoke logit math elsewhere.
- Identifier columns (GEOID, SERIALNO, w_geocode, zone ids) are **strings**;
  never let pandas infer them as integers (leading zeros).
- Geographic CRS EPSG:4326 for storage; EPSG:2229 for distance/area math.
- Module docstrings explain the *modeling* rationale, not just the code.
- Public functions: full type hints + numpy-style docstring params where
  non-obvious.
- Verify lint with the **exit code** (`ruff check src tests; echo $?`).

## Test strategy

- Every acceptance criterion in a story → at least one pytest test.
- Three mandatory test kinds per model component:
  1. **mechanics** (shapes, ids, determinism given a seed),
  2. **behavioral signature** (e.g. income ↑ ⇒ auto ownership ↑; nearer/larger
     destinations win; nesting dampens IIA),
  3. **stage integration** offline (fixture-driven `pipeline.run([...])`).
- Fixtures are tiny but *internally consistent* (e.g. popsyn controls must be
  reproducible from the seed); geometry fixtures travel as WKT CSVs.
- Tests asserting distributions use generous tolerances and fixed seeds.

## Architectural decisions of record

| # | Decision | Rationale |
|---|---|---|
| AD1 | Hybrid ActivitySim-demand / MATSim-supply | brief requirement; best-of-breed halves |
| AD2 | Tidy-tables-in-a-DataStore over a DB | inspectable, checkpointable, testable |
| AD3 | Block groups as default TAZs | available everywhere from public data |
| AD4 | RAPTOR (not CSA) for transit skims | round = transfer count falls out naturally |
| AD5 | Uniform alternative sampling in destination choice | MNL correction cancels; no bias |
| AD6 | Lazy optional imports (`geo`, `osm`) | core stays installable anywhere |
