"""Long-term and mobility choice models.

Simulated once per synthetic household/person, these condition all later travel:
how many vehicles a household owns, where its workers usually work and its
students usually study, whether a person holds a transit pass, and how often a
worker telecommutes. All are discrete-choice models on the :mod:`sbcabm.choice`
engine.
"""

from __future__ import annotations

from .auto_ownership import AUTO_OWNERSHIP_ALTS, run_auto_ownership
from .mobility import TELECOMMUTE_LEVELS, run_telecommute, run_transit_pass
from .school_location import choose_school
from .work_location import choose_workplace

__all__ = [
    "AUTO_OWNERSHIP_ALTS",
    "TELECOMMUTE_LEVELS",
    "choose_school",
    "choose_workplace",
    "run_auto_ownership",
    "run_telecommute",
    "run_transit_pass",
]
