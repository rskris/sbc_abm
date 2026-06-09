"""Daily activity & tour generation.

Turns each synthetic person into a *daily activity pattern* and a set of *tours*
(home-based excursions for a primary purpose). The sequence, all built on the
:mod:`sbcabm.choice` engine:

1. **CDAP** — a coordinated daily activity pattern per person
   (mandatory / non-mandatory / home).
2. **Tour frequency** — number of mandatory and non-mandatory tours.
3. **Tour generation** — materialize the tour list.
4. **Primary-destination choice** — where each tour goes.
5. **Scheduling** — each tour's time of day.
"""

from __future__ import annotations

from .cdap import CDAP_PATTERNS, run_cdap
from .scheduling import schedule_tours
from .tours import generate_tours, run_nonmandatory_frequency

__all__ = [
    "CDAP_PATTERNS",
    "generate_tours",
    "run_cdap",
    "run_nonmandatory_frequency",
    "schedule_tours",
]
