# Epic 7 — Calibration, validation & reporting

**Status: Done** (7.5 blocked on OD2) · Delivers FR11.
Goal: make outputs defensible (match observed data) and consumable (standard
measures and scenario comparisons).

## Stories

### 7.1 Measures stage — Done
Tidy (measure, segment, value) table: trips, trips/person, tour & trip mode
shares, person-auto VMT, transit boardings, average travel time by purpose,
and per-period network VMT/VHT; internal-consistency tests.
*Evidence:* `src/sbcabm/measures/{measures,stage}.py`; `tests/test_measures.py`.

### 7.2 Validation targets & gap report — Done
Targets CSV (measure, segment, observed, source); gap report with difference
and percent deviation, unmatched targets kept visible; wired to the measures
stage via `validation.targets_path`. Real target *data* remains OD1.
*Evidence:* `src/sbcabm/measures/validation.py`; `tests/test_measures.py`,
`tests/fixtures/validation/targets.csv`.

### 7.3 Calibration harness — Done
Damped iterative ASC adjustment (base-anchored log-ratio for all alternatives)
against any share simulator; converges below 1% on the auto-ownership spec;
calibrated specs written alongside originals, never overwriting them.
*Evidence:* `src/sbcabm/measures/calibration.py`; `tests/test_measures.py`.

### 7.4 Scenario tooling & comparison report — Done
`compare_measures` (outer-join deltas + percent) and `run_and_compare` over two
configs; identical runs produce zero deltas (deterministic given seeds).
*Evidence:* `src/sbcabm/measures/scenario.py`; `tests/test_measures.py`.

### 7.5 Live-data validation run — Draft
**AC:** documented, reproducible real-data run for SB County in a
network-enabled environment (ingest → measures), with the ACS/PUMS variable
scheme verified against the live API and popsyn diagnostics published.
*Blocked on PRD OD2 (environment network policy).*
