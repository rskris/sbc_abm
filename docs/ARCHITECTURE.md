# Architecture

This document describes the target architecture for the Santa Barbara County
activity-based model (SBC ABM). It is intentionally more complete than the
current implementation; see [`ROADMAP.md`](ROADMAP.md) for what exists today.

## Design principles

1. **Config-driven.** Every run is fully described by a YAML config plus input
   data. Code contains *logic*, not *parameters*. Utility coefficients,
   alternatives, and control totals live in data/config, mirroring ActivitySim's
   spec-file philosophy.
2. **Composable stages.** The pipeline is an ordered list of named *stages*. Each
   stage reads named tables from a shared data store, writes named tables back,
   and can be run independently for debugging or re-estimation.
3. **Reproducible.** A single random seed governs all Monte-Carlo draws. Runs are
   deterministic given (config, data, seed).
4. **Demand / supply separation.** Demand (who travels, why, where, when, how) is
   ActivitySim-inspired discrete choice. Supply (how the network performs under
   load) is MATSim-inspired agent simulation. They communicate only through
   **skims** (level-of-service matrices) and **plans/trip lists**, and iterate to
   equilibrium.
5. **Public data first.** No proprietary inputs are required to stand up a
   baseline model. See [`DATA_SOURCES.md`](DATA_SOURCES.md).

## System overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  DATA LAYER  (src/sbcabm/data)                                         │
│  census (ACS, PUMS) · geographies (TIGER) · employment (LODES) ·       │
│  networks (OSM) · transit (GTFS)        →  cached, versioned tables    │
└──────────────────────────────────────────────────────────────────────┘
            │ marginals, seed households, zone attributes
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  ZONE SYSTEM  (src/sbcabm/zones)                                       │
│  TAZ / block-group geographies, centroids, land use, accessibility    │
└──────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  DEMAND  (ActivitySim-inspired discrete choice)                       │
│                                                                        │
│  popsyn        synthetic households + persons (IPF/IPU + integerize)   │
│  longterm      usual workplace & school location, auto ownership,      │
│                transit pass, telecommute frequency                     │
│  activitygen   coordinated daily activity pattern (CDAP), mandatory /  │
│                non-mandatory tour frequency                            │
│  tours         tour scheduling (time-of-day), primary destination     │
│  modechoice    tour & trip mode choice (nested logit)                  │
│  trips         intermediate-stop generation, trip departure, trip mode │
│                                                                        │
│  → trip list / agent plans                                             │
└──────────────────────────────────────────────────────────────────────┘
            │ plans                                  ▲ skims
            ▼                                        │
┌──────────────────────────────────────────────────────────────────────┐
│  SUPPLY  (MATSim-inspired agent simulation)                           │
│  network model · mobsim (queue / volume-delay loading) · scoring ·    │
│  co-evolutionary re-planning  →  link volumes, transit loads, skims   │
└──────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  MEASURES / REPORTING                                                  │
│  VMT, mode share, transit ridership, accessibility, emissions, equity │
└──────────────────────────────────────────────────────────────────────┘
```

The outer loop (demand → supply → updated skims → demand …) iterates until
travel times stabilize ("system equilibrium"), exactly as ActivitySim feeds a
static assignment, but here using a MATSim-style dynamic loading.

## Module responsibilities

### Data layer (`data/`)
- `sources.py` — a registry describing every public dataset (URL templates,
  geography, vintage, license) so ingestion is declarative and auditable.
- `census.py` — ACS marginal tables and PUMS seed records via the Census API,
  with on-disk caching. Produces the **control totals** and **seed households**
  that population synthesis consumes.
- `geographies.py` *(planned)* — TIGER/Line block groups, tracts, PUMAs; the
  spatial backbone for zones.

### Zone system (`zones/`)
- A `ZoneSystem` ties model zones (TAZs, or block groups as a default) to their
  geometry, centroids, and zonal attributes (population, employment by sector,
  households, area, density). Provides ID lookups and adjacency used downstream.

### Population synthesis (`popsyn/`) — **implemented**
Reproduces a synthetic population whose aggregate characteristics match Census
control totals while preserving the joint distributions found in PUMS micro-data.
- `ipf.py` — N-dimensional Iterative Proportional Fitting (Deming–Stephan).
- `balancer.py` — list balancing / Iterative Proportional Updating (IPU): solves
  for per-household weights matching many marginal controls simultaneously, at
  both household and person level.
- `integerize.py` — convert fractional weights to integer household counts that
  still sum to the control totals (largest-remainder allocation).
- `synthesizer.py` — orchestrates balancing + integerizing + expansion into a
  concrete table of synthetic households and persons per zone.

### Demand models (`longterm/`, `activitygen/`, `tours/`, `modechoice/`) — *planned*
Each is a discrete-choice model evaluated against a **utility spec** (a CSV of
expressions × coefficients), following ActivitySim's design so coefficients can
be re-estimated without code changes. See the roadmap for sequencing.

### Supply / assignment (`assignment/`, `skims/`) — *planned*
- `skims/` — origin-destination level-of-service matrices (time, distance, cost)
  by mode and time period; the contract between demand and supply.
- `assignment/` — MATSim-style mobsim with per-agent plan scoring and
  co-evolutionary re-planning, plus static volume-delay fallback for fast runs.

## The data store & pipeline contract

Stages do not call each other directly. The orchestrator (`pipeline.py`) owns a
**data store** (a dict of named `pandas`/`geopandas` tables, checkpointed to
disk). Each stage declares the tables it `reads` and `writes`. This makes the
pipeline inspectable, resumable from any checkpoint, and easy to test stage by
stage — the same properties that make ActivitySim debuggable on large regions.

## Coordinate reference & units

- Geographies are processed in **EPSG:4326** (lat/lon) for ingestion and
  reprojected to **EPSG:2229** (California State Plane Zone 5, US feet) — the
  appropriate projected CRS for Santa Barbara County — for distance/area work.
- Times are minutes after midnight; monetary units are year-2020 USD unless a
  config deflator is set.
