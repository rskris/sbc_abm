# Epic 4 — Daily activities & tours

**Status: Done** · Delivers FR8.
Goal: each synthetic person gets a coordinated day pattern and scheduled,
destination-assigned tours.

## Stories

### 4.1 Household-interaction CDAP — Done
Joint household pattern choice: member-pattern combinations enumerated (cap 5
modeled members, overflow independent) with pairwise interaction terms;
coordination (both-home) measurably higher than the independent model.
*Evidence:* `src/sbcabm/activitygen/cdap.py`; `tests/test_activitygen_phase4.py`.

### 4.2 Tour frequency & generation — Done
Mandatory tour per mandatory-pattern person (work/school by usual location);
non-mandatory count MNL with availability (nm_0 barred for nonmandatory
pattern); tour list with category/purpose/home zone.
*Evidence:* `src/sbcabm/activitygen/tours.py`; `tests/test_activitygen.py`.

### 4.3 Joint household tours — Done
Eligible households (≥2 leaving home) may make one fully-joint tour;
participants share `joint_tour_id`, one destination, one schedule.
*Evidence:* `src/sbcabm/activitygen/joint_tours.py`; `tests/test_activitygen_phase4.py`.

### 4.4 Tour destinations — Done
Work→workplace, school→school zone; others via destination engine with
purpose-specific size terms; joint pre-assigned destinations preserved.
*Evidence:* `src/sbcabm/activitygen/tours.py::assign_destinations`.

### 4.5 Discrete time-of-day — Done
MNL over enumerated (start, end) windows penalizing deviation from
purpose-preferred timing; purpose ordering and reproducibility asserted.
*Evidence:* `src/sbcabm/activitygen/scheduling.py`; `tests/test_activitygen_phase4.py`.
