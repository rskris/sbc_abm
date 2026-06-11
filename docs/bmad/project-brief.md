# Project Brief — SBC ABM

**Status:** Approved · **Owner:** rskris · **Analyst pass:** 2026-06

## Problem statement

Santa Barbara County needs a transparent, modern travel demand model. Regional
agencies increasingly require *activity-based* models (ABMs) — which simulate
individual people's daily schedules rather than aggregate trip tables — to
analyze transit investments, land-use change, pricing, and equity. Commercial
models are opaque and expensive; existing open frameworks (ActivitySim, MATSim)
each cover only half the problem (demand vs. supply).

## Product vision

An open-source, production-oriented ABM for Santa Barbara County that:

- combines **ActivitySim-style discrete-choice demand** modeling with
  **MATSim-style agent-based network supply**,
- is bootstrapped **entirely from free public data** (Census ACS/PUMS, LODES,
  TIGER, Gazetteer, OSM, GTFS) so it can be stood up with zero procurement,
- is **config-driven** (coefficients and specs are data) so planners can
  recalibrate without touching code, and
- runs **offline against fixtures** for development and CI, and against live
  public APIs for real runs.

## Target users

1. **Regional planners** (SBCAG and city staff) — scenario analysis, forecasts.
2. **Researchers/students** — a readable, tested reference ABM.
3. **Contributors** — an extensible platform with clean stage contracts.

## Success criteria

- Full pipeline runs end-to-end from public data to network measures.
- Each model component is unit-tested with behavioral assertions.
- A documented path to calibration against observed data (NHTS/CHTS, counts).
- A planner can change a coefficient or control scheme without writing Python.

## Constraints & assumptions

- Public data only; no proprietary inputs required for the baseline.
- Python ≥ 3.10; heavy geospatial/OSM dependencies isolated in optional extras.
- Development environments may lack outbound network access — every stage must
  degrade to bundled fixtures.
- Single-machine execution for the county scale (~400 block groups, ~450k pop).

## Out of scope (for v1)

- Freight/commercial vehicle models; external (gateway) travel beyond simple
  assumptions; land-use forecasting (inputs are exogenous); microsimulation of
  pedestrian dynamics.
