"""Mode and trip models.

The demand side's final step: assign a travel mode to each tour (a nested logit
over the multimodal skims), break tours into trips with intermediate stops, and
give each trip a mode and a departure time — producing the trip list that the
network-assignment supply side will load.
"""

from __future__ import annotations

from .los import build_mode_los
from .tour_mode import TOUR_MODE_NESTS, TOUR_MODES, run_tour_mode_choice
from .trips import generate_trips

__all__ = [
    "TOUR_MODES",
    "TOUR_MODE_NESTS",
    "build_mode_los",
    "generate_trips",
    "run_tour_mode_choice",
]
