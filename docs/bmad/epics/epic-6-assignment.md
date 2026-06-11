# Epic 6 — Assignment & equilibrium

**Status: Draft** · Delivers FR10.
Goal: load the trip list onto the network, produce congested travel times and
link volumes, and iterate demand↔supply to equilibrium — closing the loop that
makes the model a *system*, not a one-way pipeline.

## Stories

### 6.1 Static BPR assignment — Approved (next up)
*As a* modeler *I want* auto trips assigned to network links with volume-delay
feedback *so that* congested link times and volumes exist.
**Acceptance criteria**
1. `assignment/static.py` assigns period-grouped auto trips to shortest paths
   and updates link times with the BPR function
   `t = t0 · (1 + α(v/c)^β)` (defaults α=0.15, β=4; capacities derived from
   link class/lanes with documented defaults).
2. Iterative loading (MSA — method of successive averages) converges: max
   relative link-time change < tolerance or max iterations; convergence
   diagnostics returned.
3. Produces `link_volumes` (per link, per period) and `congested_times`.
4. Offline stage test: fixture trips load, volumes are conserved (sum of
   assigned trips = auto trips), congested time ≥ free-flow time.
Full sharded story: [`../stories/6.1.static-bpr-assignment.md`](../stories/6.1.static-bpr-assignment.md).

### 6.2 Congested skims & demand feedback — Draft
*As a* modeler *I want* congested times fed back into skims and the demand
stages re-run *so that* mode/destination choices respond to congestion.
**AC:** `skims` stage can rebuild from `congested_times` by period; an outer
`equilibrium` loop (configurable iterations) re-runs demand → assignment →
skims; documented convergence metric (skim RMSE between iterations) decreases;
reproducible given seed.

### 6.3 Agent plans & scoring (MATSim-style) — Draft
*As a* modeler *I want* each person's day expressed as a scored plan *so that*
co-evolutionary replanning is possible.
**AC:** `plans` table (person → ordered activities+legs with times/modes);
Charypar–Nagel-style score (activity utility + travel disutility) computed per
plan from assigned times; scores reproducible.

### 6.4 Co-evolutionary replanning — Draft
*As a* modeler *I want* a fraction of agents to mutate plans (re-route,
re-time, re-mode) each iteration, keeping better-scoring plans *so that* the
population self-organizes toward equilibrium.
**AC:** plan memory (configurable size) per agent; selection by score
(logit/best); average population score non-decreasing over iterations on the
fixture network; iteration history exposed for diagnostics.

### 6.5 Time-period capacities & convergence diagnostics — Draft
**AC:** per-period (EA/AM/MD/PM/EV) assignment using trip `depart_hour`;
relative gap + skim-change reported per iteration; `measures`-ready outputs.
