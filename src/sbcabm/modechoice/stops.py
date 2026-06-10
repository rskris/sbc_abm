"""Intermediate-stop frequency and purpose models.

Two models that shape how tours break into trips:

* **Stop frequency** — a *joint half-tour* choice: one multinomial logit picks the
  number of stops on the outbound and inbound half-tours together (0–2 each), so
  the two directions are chosen jointly rather than independently
  (``configs/specs/stop_frequency.csv``).
* **Stop purpose** — each stop's activity purpose, drawn from a distribution that
  depends on the tour's primary purpose.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..choice import mnl_simulate

logger = logging.getLogger("sbcabm.modechoice.stops")

# Alternative label → (outbound stops, inbound stops).
STOP_FREQUENCY_ALTS = {
    "s0_0": (0, 0),
    "s1_0": (1, 0),
    "s0_1": (0, 1),
    "s1_1": (1, 1),
    "s2_0": (2, 0),
    "s0_2": (0, 2),
    "s2_1": (2, 1),
    "s1_2": (1, 2),
    "s2_2": (2, 2),
}

# Tour purpose → stop-purpose distribution. Stop purposes map to size terms in
# trips.py (shopping→retail, other/eatout→service).
_STOP_PURPOSE_DIST = {
    "work": {"shopping": 0.3, "other": 0.4, "eatout": 0.3},
    "school": {"shopping": 0.2, "other": 0.6, "eatout": 0.2},
    "shopping": {"shopping": 0.4, "other": 0.4, "eatout": 0.2},
    "other": {"shopping": 0.2, "other": 0.6, "eatout": 0.2},
}
_DEFAULT_DIST = _STOP_PURPOSE_DIST["other"]


def run_stop_frequency(
    tours: pd.DataFrame, spec: pd.DataFrame, *, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Choose joint (outbound, inbound) stop counts for each tour.

    Returns two integer arrays aligned to ``tours``: outbound and inbound stop
    counts (0–2 each).
    """
    if tours.empty:
        return np.zeros(0, dtype=int), np.zeros(0, dtype=int)
    choices = mnl_simulate(tours, spec, rng=rng)
    pairs = choices.map(STOP_FREQUENCY_ALTS)
    out_stops = pairs.map(lambda t: t[0]).to_numpy(dtype=int)
    in_stops = pairs.map(lambda t: t[1]).to_numpy(dtype=int)
    logger.info(
        "stop frequency: %.2f stops/tour avg",
        (out_stops.sum() + in_stops.sum()) / max(len(tours), 1),
    )
    return out_stops, in_stops


def sample_stop_purpose(tour_purpose: str, rng: np.random.Generator) -> str:
    """Draw a stop activity purpose given the tour's primary purpose."""
    dist = _STOP_PURPOSE_DIST.get(tour_purpose, _DEFAULT_DIST)
    purposes = list(dist)
    probabilities = np.array(list(dist.values()))
    return purposes[rng.choice(len(purposes), p=probabilities)]
