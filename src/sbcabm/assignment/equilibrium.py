"""The demand↔supply equilibrium loop (story 6.2).

Iterates: mode/trip choice on current skims → static assignment → congested
auto skims → replace the auto LOS → repeat. Convergence is tracked as the RMSE
between successive iterations' auto skim times; under fixed activity patterns
this contracts toward a fixed point (congestion-consistent demand).

Configured via an optional ``equilibrium:`` block in the run config:

    equilibrium:
      iterations: 3
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..config import Config
from ..modechoice.stage import run_modechoice
from ..network.graph import Network
from ..pipeline import DataStore
from ..skims.congested import collapse_to_representative, congested_auto_skims
from .static import assign_static
from .summary import network_summary

logger = logging.getLogger("sbcabm.assignment.equilibrium")

_DEFAULT_ITERATIONS = 3


def run_equilibrium(config: Config, store: DataStore) -> None:
    for table in ("tours", "skims", "network_nodes", "network_links", "zone_connectors"):
        if not store.has(table):
            raise KeyError(f"equilibrium requires '{table}'; run earlier stages first")

    settings = (config.raw or {}).get("equilibrium", {})
    iterations = int(settings.get("iterations", _DEFAULT_ITERATIONS))

    network = Network.from_tables(store.get("network_nodes"), store.get("network_links"))
    connectors = store.get("zone_connectors")
    base_auto = store.get("skims").query("mode == 'auto'").copy()

    previous = _auto_time_vector(store.get("skims"))
    history = []
    for k in range(1, iterations + 1):
        run_modechoice(config, store)  # re-choose modes under current skims
        result = assign_static(store.get("trips"), network, connectors)

        per_period = congested_auto_skims(result.congested_times, connectors, base_auto)
        representative = collapse_to_representative(per_period)
        if not representative.empty:
            others = store.get("skims").query("mode != 'auto'")
            store.put("skims", pd.concat([others, representative], ignore_index=True))
        store.put("link_volumes", result.link_volumes)
        store.put("congested_times", result.congested_times)
        store.put("assignment_diagnostics", result.diagnostics)
        store.put(
            "network_summary",
            network_summary(result.link_volumes, result.congested_times, network),
        )

        current = _auto_time_vector(store.get("skims"))
        rmse = _rmse(previous, current)
        previous = current
        mean_gap = (
            float(result.diagnostics["relative_gap"].mean())
            if len(result.diagnostics)
            else 0.0
        )
        history.append(
            {"iteration": k, "skim_rmse": rmse, "mean_assignment_gap": mean_gap}
        )
        logger.info("equilibrium iter %d: skim RMSE %.4f, mean gap %.4f", k, rmse, mean_gap)

    store.put("equilibrium_history", pd.DataFrame(history))


def _auto_time_vector(skims: pd.DataFrame) -> pd.Series:
    auto = skims[skims["mode"] == "auto"]
    return auto.set_index(["origin_zone", "dest_zone"])["time_min"].sort_index()


def _rmse(previous: pd.Series, current: pd.Series) -> float:
    aligned = pd.concat([previous, current], axis=1, keys=["a", "b"]).dropna()
    if aligned.empty:
        return 0.0
    return float(np.sqrt(((aligned["a"] - aligned["b"]) ** 2).mean()))
