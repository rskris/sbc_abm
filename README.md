# SBC ABM — Santa Barbara County Activity-Based Travel Demand Model

An open, production-oriented **activity-based model (ABM)** for travel demand in
Santa Barbara County, California.

The design borrows from two mature ecosystems:

- **[ActivitySim](https://activitysim.github.io/)** — for the *demand* side:
  discrete-choice (logit) models of synthetic travelers' long-term choices,
  daily activity patterns, tours, and trips.
- **[MATSim](https://www.matsim.org/)** — for the *supply* side: agent-based,
  co-evolutionary network loading where each traveler iteratively re-plans to
  improve a utility ("score") under congestion.

The whole model is bootstrapped from **public data** (US Census/ACS & PUMS,
LEHD/LODES, TIGER/Line, OpenStreetMap, GTFS) — see
[`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

> **Status:** early development. The population-synthesis core is implemented and
> tested; remaining pipeline stages are scaffolded with a documented roadmap.
> See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## What an ABM does

Instead of aggregate "four-step" trip tables, an ABM simulates a **synthetic
population** of individual households and persons, then predicts each person's
*daily schedule of activities* (home, work, school, shop, …) and the *trips*
that connect them — including when they travel, where, and by which mode. Those
trips are then loaded onto a multimodal network to estimate congestion, transit
ridership, emissions, and accessibility.

```
public data ─▶ zones ─▶ synthetic population ─▶ long-term choices
                                                      │
                            ┌─────────────────────────┘
                            ▼
        daily activity pattern ─▶ tours ─▶ trips (mode/dest/time)
                            │
                            ▼
        network assignment (co-evolutionary) ─▶ skims ─▶ (feedback)
                            │
                            ▼
              measures: VMT, mode share, ridership, accessibility
```

## Quick start

```bash
# Install the package (editable) with dev tooling
pip install -e ".[dev]"

# Run the test suite
pytest

# Inspect the configuration and pipeline stages
sbcabm info
sbcabm run --stages popsyn --config configs/settings.yaml
```

> Live data ingestion (Census API, TIGER, OSM, GTFS) requires outbound network
> access. Where the network is restricted, the pipeline runs against the small
> fixtures in `tests/fixtures/` so the mechanics can be exercised offline.

## Repository layout

```
configs/            run configuration (YAML)
docs/               architecture, roadmap, data sources
src/sbcabm/
  config.py         typed configuration loader
  pipeline.py       stage registry + orchestrator
  cli.py            `sbcabm` command-line entry point
  data/             public-data ingestion (census, geographies, sources)
  zones/            zone system (TAZ / block-group)
  popsyn/           population synthesis (IPF, list balancing, integerizer)
  # forthcoming: longterm/ activitygen/ tours/ modechoice/ skims/ assignment/
tests/              unit tests + fixtures
```

## License

MIT — see [`LICENSE`](LICENSE).
