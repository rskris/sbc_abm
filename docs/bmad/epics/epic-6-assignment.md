# Epic 6 — Assignment & equilibrium

**Status: Done** · Delivers FR10.
Goal: load the trip list onto the network, produce congested travel times and
link volumes, and iterate demand↔supply to equilibrium — closing the loop that
makes the model a *system*, not a one-way pipeline.

## Stories

### 6.1 Static BPR assignment — Done
Period-grouped auto trips assigned by MSA-averaged all-or-nothing shortest
paths with BPR volume-delay (α=0.15, β=4; documented lane/capacity defaults;
per-mode occupancy divisor). Produces `link_volumes`, `congested_times`,
`assignment_diagnostics`; deterministic; conservation, monotonicity,
convergence, and stage integration all asserted.
*Evidence:* `src/sbcabm/assignment/{static,stage}.py`; `tests/test_assignment.py`.
Story file: [`../stories/6.1.static-bpr-assignment.md`](../stories/6.1.static-bpr-assignment.md).

### 6.2 Congested skims & demand feedback — Done
Per-period congested auto skims rebuilt from assignment times (distance from
the free-flow skim), collapsed to a representative auto LOS; `equilibrium`
stage loops modechoice → assignment → skims with skim-RMSE convergence history.
*Evidence:* `src/sbcabm/skims/congested.py`,
`src/sbcabm/assignment/equilibrium.py`; `tests/test_equilibrium.py`.

### 6.3 Agent plans & scoring (MATSim-style) — Done
`plans` table (alternating activities/legs per person, day closing at 24:00);
Charypar–Nagel scoring (activity ln-utility with 3-min floor, per-mode travel
disutility), congested-auto-aware time lookup; `plans` stage.
*Evidence:* `src/sbcabm/assignment/{plans,plans_stage}.py`; `tests/test_plans.py`.

### 6.4 Co-evolutionary replanning — Done
Per-agent strategy memory (configurable size), best-score selection,
TOD/mode mutation for a replan share, congestion-aware rescoring each
iteration; average best-remembered score provably non-decreasing; history
exposed; final state adopts each agent's best strategy. Run explicitly as the
`replanning` stage.
*Evidence:* `src/sbcabm/assignment/replanning.py`; `tests/test_replanning.py`.

### 6.5 Time-period capacities & convergence diagnostics — Done
Per-period assignment landed with 6.1; per-iteration gap/skim-RMSE with 6.2;
this story adds the measures-ready `network_summary` (per-period VMT, VHT,
average speed, volume-weighted congestion ratio).
*Evidence:* `src/sbcabm/assignment/summary.py`; `tests/test_network_summary.py`.
