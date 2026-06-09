"""The ``modechoice`` pipeline stage: tour mode choice and trip generation.

Assigns a mode to every tour (nested logit over the skims), then breaks tours
into a trip list with intermediate stops. Writes ``tour_mode`` onto ``tours`` and
a new ``trips`` table.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from ..choice import load_spec
from ..config import Config
from ..pipeline import DataStore
from .tour_mode import run_tour_mode_choice
from .trips import generate_trips

logger = logging.getLogger("sbcabm.modechoice")


def run_modechoice(config: Config, store: DataStore) -> None:
    for table in ("tours", "households", "zones", "skims"):
        if not store.has(table):
            raise KeyError(f"modechoice requires '{table}'; run earlier stages first")

    rng = np.random.default_rng(config.random_seed)
    tours = store.get("tours").copy()
    households = store.get("households")
    skims = store.get("skims")
    transit_skims = store.get("transit_skims") if store.has("transit_skims") else None

    spec = load_spec(_spec(config, "tour_mode_choice.csv"))
    tours["tour_mode"] = run_tour_mode_choice(
        tours, households, skims, spec, transit_skims=transit_skims, rng=rng
    ).to_numpy()
    store.put("tours", tours)

    auto_skim = skims.query("mode == 'auto'")
    trips = generate_trips(tours, store.get("zones"), auto_skim, rng=rng)
    store.put("trips", trips)
    logger.info("modechoice: %d tours moded, %d trips generated", len(tours), len(trips))


def _spec(config: Config, name: str) -> Path:
    candidate = config.config_dir / "specs" / name
    return candidate if candidate.exists() else Path("configs/specs") / name
