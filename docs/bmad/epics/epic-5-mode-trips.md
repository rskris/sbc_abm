# Epic 5 — Mode & trips

**Status: Done** · Delivers FR9.
Goal: assign modes and emit the final trip list the supply side will load.

## Stories

### 5.1 Per-tour level-of-service — Done
Auto/walk/bike time & distance from road skims, transit time from RAPTOR skims,
auto operating cost + flat fare; NaN ⇒ mode unavailable at that OD.
*Evidence:* `src/sbcabm/modechoice/los.py`; `tests/test_modechoice.py`.

### 5.2 Tour mode choice — Done
Nested logit (auto / transit / active) over five modes,
`configs/specs/tour_mode_choice.csv`; availability gates by reachability,
walk/bike time caps, vehicle access (carless ⇒ never drive-alone).
*Evidence:* `src/sbcabm/modechoice/tour_mode.py`; `tests/test_modechoice.py`.

### 5.3 Joint half-tour stop frequency & purpose — Done
One MNL over joint (outbound, inbound) stop counts (0–2 each,
`configs/specs/stop_frequency.csv`); stop purposes drawn conditioned on tour
purpose (shopping/other/eatout).
*Evidence:* `src/sbcabm/modechoice/stops.py`; `tests/test_modechoice_phase5.py`.

### 5.4 Trip generation — Done
Tours decompose into legs through their stops; departure times spread across
the tour window; supports multiple stops per direction.
*Evidence:* `src/sbcabm/modechoice/trips.py`; `tests/test_modechoice_phase5.py`.

### 5.5 Trip mode choice — Done
Each trip re-chooses its mode on its own OD LOS via the nested logit,
constrained to the tour-mode-consistent set (tour's own mode always available);
carless constraint holds at trip level.
*Evidence:* `src/sbcabm/modechoice/trip_mode.py`; `tests/test_modechoice_phase5.py`.
