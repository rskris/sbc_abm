"""Long-term and mobility choice models.

These are simulated once per synthetic household/person and condition all later
travel: how many vehicles a household owns and where its workers usually work.
Both are discrete-choice models built on the :mod:`sbcabm.choice` engine.
"""

from __future__ import annotations

from .auto_ownership import AUTO_OWNERSHIP_ALTS, run_auto_ownership
from .work_location import choose_workplace

__all__ = ["AUTO_OWNERSHIP_ALTS", "choose_workplace", "run_auto_ownership"]
