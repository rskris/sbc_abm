"""The ``plans`` pipeline stage: build and score agent day plans.

Reads ``trips``, ``skims`` (and optionally ``transit_skims`` and the congested
auto skims already folded into ``skims`` by the equilibrium loop) and writes a
``plans`` table plus per-person ``plan_scores``.
"""

from __future__ import annotations

import logging

from ..config import Config
from ..pipeline import DataStore
from .plans import build_plans, make_time_lookup, score_plans

logger = logging.getLogger("sbcabm.assignment.plans")


def run_plans(config: Config, store: DataStore) -> None:
    for table in ("trips", "skims"):
        if not store.has(table):
            raise KeyError(f"plans requires '{table}'; run earlier stages first")

    transit = store.get("transit_skims") if store.has("transit_skims") else None
    lookup = make_time_lookup(store.get("skims"), transit)
    plans = build_plans(store.get("trips"), lookup)
    scores = score_plans(plans)

    store.put("plans", plans)
    store.put("plan_scores", scores.reset_index())
    logger.info(
        "plans: %d elements for %d persons (mean score %.2f)",
        len(plans),
        scores.size,
        float(scores.mean()) if scores.size else 0.0,
    )
