"""The ``modechoice`` pipeline stage: tour & trip mode choice and trip generation.

Assigns a mode to every tour (nested logit over the skims), chooses the number
and purpose of intermediate stops, breaks tours into trips, then re-chooses each
trip's mode consistently with its tour. Writes ``tour_mode`` onto ``tours`` and a
new ``trips`` table.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from ..choice import load_spec
from ..config import Config
from ..pipeline import DataStore
from .stops import run_stop_frequency
from .tour_mode import run_tour_mode_choice
from .trip_mode import run_trip_mode_choice
from .trips import generate_trips

logger = logging.getLogger("sbcabm.modechoice")


def run_modechoice(config: Config, store: DataStore) -> None:
    for table in ("tours", "households", "zones", "skims"):
        if not store.has(table):
            raise KeyError(f"modechoice requires '{table}'; run earlier stages first")

    rng = np.random.default_rng(config.random_seed)
    tours = store.get("tours").copy()
    households = store.get("households")
    zones = store.get("zones")
    skims = store.get("skims")
    transit_skims = store.get("transit_skims") if store.has("transit_skims") else None

    mode_spec = load_spec(_spec(config, "tour_mode_choice.csv"))
    tours["tour_mode"] = run_tour_mode_choice(
        tours, households, skims, mode_spec, transit_skims=transit_skims, rng=rng
    ).to_numpy()
    store.put("tours", tours)

    # Joint half-tour stop frequency → trip list with intermediate stops.
    freq_spec = load_spec(_spec(config, "stop_frequency.csv"))
    out_stops, in_stops = run_stop_frequency(tours, freq_spec, rng=rng)
    auto_skim = skims.query("mode == 'auto'")
    trips = generate_trips(tours, zones, auto_skim, rng=rng, out_stops=out_stops, in_stops=in_stops)

    # Trip mode choice (consistent with the tour mode).
    trips["mode"] = run_trip_mode_choice(
        trips, tours, households, skims, mode_spec, transit_skims=transit_skims, rng=rng
    ).to_numpy()
    store.put("trips", trips)
    logger.info("modechoice: %d tours moded, %d trips generated", len(tours), len(trips))


def _spec(config: Config, name: str) -> Path:
    candidate = config.config_dir / "specs" / name
    return candidate if candidate.exists() else Path("configs/specs") / name
