# Epic 7 — Calibration, validation & reporting

**Status: Draft** · Delivers FR11.
Goal: make outputs defensible (match observed data) and consumable (standard
measures and scenario comparisons).

## Stories

### 7.1 Measures stage — Draft
*As a* planner *I want* standard summaries from any run *so that* results are
comparable across scenarios.
**AC:** `measures` stage computes VMT (person & vehicle), mode shares (tour and
trip level), transit boardings, average travel times by purpose, and
trips-per-person, written as tidy tables; offline test asserts internal
consistency (e.g. VMT = Σ trip distance by auto modes).

### 7.2 Validation targets & gap report — Draft
*As a* modeler *I want* model summaries compared against observed targets
(NHTS/CHTS rates, ACS commute shares, counts where available) *so that* error
is quantified.
**AC:** target file format (CSV: measure, segment, observed value, source);
gap report table + percent deviation; CI-runnable on fixture targets.
*Blocked on PRD OD1 (target data choice).*

### 7.3 Calibration harness — Draft
*As a* modeler *I want* automated adjustment of alternative-specific constants
*so that* simulated shares match targets without manual iteration.
**AC:** iterative ASC adjustment (`Δ = ln(observed/modeled)`) for chosen models
(mode choice, auto ownership) with damping; converges on fixtures; writes
calibrated spec CSVs alongside originals (never overwrites the estimated spec).

### 7.4 Scenario tooling & comparison report — Draft
**AC:** run two configs (base vs scenario) and emit a comparison of measures
with absolute/percent deltas; deterministic given seeds.

### 7.5 Live-data validation run — Draft
**AC:** documented, reproducible real-data run for SB County in a
network-enabled environment (ingest → measures), with the ACS/PUMS variable
scheme verified against the live API and popsyn diagnostics published.
*Blocked on PRD OD2 (environment network policy).*
