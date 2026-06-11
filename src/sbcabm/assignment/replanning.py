"""Co-evolutionary replanning (story 6.4) — the MATSim-style supply loop.

Each agent (person) holds a small **memory** of strategies — variants of their
day differing in time-of-day and tour mode — each tagged with the score it
earned when last executed. Every iteration:

1. a fraction of agents **mutate**: they re-draw their tours' time-of-day or
   re-choose their tour modes (innovation);
2. the rest **select** their best-remembered strategy (exploitation);
3. the whole population's chosen strategies are turned into trips, assigned to
   the network, and **scored** under the resulting congestion;
4. each agent's memory absorbs the executed (strategy, score), trimmed to the
   ``memory_size`` best.

Because memories only ever absorb new scores and keep the best, the average
best-remembered score is non-decreasing — the population co-evolves toward a
mutually consistent (congestion-aware) set of day plans.

During replanning, trips inherit their tour's mode and carry no intermediate
stops (the strategy space is time-of-day × mode; stop patterns stay fixed) —
a documented simplification.

Configured via an optional ``replanning:`` block:

    replanning:
      iterations: 4
      replan_share: 0.3
      memory_size: 3
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..activitygen.scheduling import choose_time_of_day
from ..choice import load_spec
from ..config import Config
from ..modechoice.stage import _spec as _mode_spec_path
from ..modechoice.tour_mode import run_tour_mode_choice
from ..modechoice.trips import generate_trips
from ..network.graph import Network
from ..pipeline import DataStore
from ..skims.congested import collapse_to_representative, congested_auto_skims
from .plans import build_plans, make_time_lookup, score_plans
from .static import assign_static

logger = logging.getLogger("sbcabm.assignment.replanning")

_DEFAULTS = {"iterations": 4, "replan_share": 0.3, "memory_size": 3}


def run_replanning(config: Config, store: DataStore) -> None:
    required = ("tours", "households", "zones", "skims", "network_nodes",
                "network_links", "zone_connectors")
    for table in required:
        if not store.has(table):
            raise KeyError(f"replanning requires '{table}'; run earlier stages first")

    settings = {**_DEFAULTS, **(config.raw or {}).get("replanning", {})}
    iterations = int(settings["iterations"])
    replan_share = float(settings["replan_share"])
    memory_size = int(settings["memory_size"])

    rng = np.random.default_rng(config.random_seed)
    households = store.get("households")
    zones = store.get("zones")
    skims = store.get("skims")
    transit = store.get("transit_skims") if store.has("transit_skims") else None
    network = Network.from_tables(store.get("network_nodes"), store.get("network_links"))
    connectors = store.get("zone_connectors")
    auto_skim = skims.query("mode == 'auto'")
    mode_spec = load_spec(_mode_spec_path(config, "tour_mode_choice.csv"))

    tours = store.get("tours").reset_index(drop=True)
    person_ids = list(tours["person_id"].unique())
    current = {pid: grp.copy() for pid, grp in tours.groupby("person_id", sort=False)}
    memory: dict = {pid: [] for pid in person_ids}

    history = []
    for k in range(1, iterations + 1):
        replanners = [pid for pid in person_ids if rng.random() < replan_share] if k > 1 else []
        for pid in person_ids:
            if pid in replanners:
                current[pid] = _mutate(
                    current[pid], rng, zones, households, skims, transit, mode_spec
                )
            elif memory[pid]:
                current[pid] = max(memory[pid], key=lambda m: m["score"])["tours"]

        population = pd.concat(current.values(), ignore_index=True)
        trips = generate_trips(population, zones, auto_skim, rng=rng, stop_probability=0.0)
        result = assign_static(trips, network, connectors)
        congested = collapse_to_representative(
            congested_auto_skims(result.congested_times, connectors, auto_skim)
        )
        lookup = make_time_lookup(skims, transit, congested_auto=congested)
        scores = score_plans(build_plans(trips, lookup))

        for pid in person_ids:
            score = float(scores.get(pid, 0.0))
            memory[pid].append({"tours": current[pid], "score": score})
            memory[pid] = sorted(memory[pid], key=lambda m: -m["score"])[:memory_size]

        avg_executed = float(scores.mean()) if scores.size else 0.0
        avg_best = float(np.mean([memory[pid][0]["score"] for pid in person_ids]))
        history.append(
            {
                "iteration": k,
                "avg_executed_score": avg_executed,
                "avg_best_score": avg_best,
                "n_replanned": len(replanners),
            }
        )
        logger.info(
            "replanning iter %d: executed %.2f, best %.2f, %d replanned",
            k, avg_executed, avg_best, len(replanners),
        )

    # Adopt every agent's best-remembered strategy as the final state.
    final = pd.concat(
        [max(memory[pid], key=lambda m: m["score"])["tours"] for pid in person_ids],
        ignore_index=True,
    )
    final_trips = generate_trips(final, zones, auto_skim, rng=rng, stop_probability=0.0)
    store.put("tours", final)
    store.put("trips", final_trips)
    store.put("replanning_history", pd.DataFrame(history))


def _mutate(person_tours, rng, zones, households, skims, transit, mode_spec):
    """Innovate one agent's strategy: re-draw time-of-day or tour modes."""
    mutated = person_tours.copy()
    if rng.random() < 0.5:
        keep = [c for c in mutated.columns if c not in ("start_hour", "end_hour", "period")]
        mutated = choose_time_of_day(mutated[keep], rng=rng)
    else:
        mutated["tour_mode"] = run_tour_mode_choice(
            mutated, households, skims, mode_spec, transit_skims=transit, rng=rng
        ).to_numpy()
    return mutated
