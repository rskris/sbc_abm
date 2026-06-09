"""Population synthesis.

Produces a synthetic population of households and persons whose aggregate
characteristics match Census control totals, while preserving the joint
distributions observed in PUMS micro-data.

Pipeline:
    1. :func:`~sbcabm.popsyn.balancer.balance_weights` (IPU) — solve for
       per-seed-household weights matching many marginal controls at once.
    2. :func:`~sbcabm.popsyn.integerize.integerize_weights` — turn fractional
       weights into integer household counts summing to the control total.
    3. :func:`~sbcabm.popsyn.synthesizer.synthesize` — expand into concrete
       household + person tables per zone.

:mod:`~sbcabm.popsyn.ipf` provides classic N-dimensional Iterative Proportional
Fitting, used for seeding/validation and available for table-balancing tasks.
"""

from __future__ import annotations

from .balancer import BalanceResult, balance_weights
from .integerize import integerize_weights
from .ipf import ipf
from .synthesizer import SynthesisResult, synthesize

__all__ = [
    "BalanceResult",
    "SynthesisResult",
    "balance_weights",
    "integerize_weights",
    "ipf",
    "synthesize",
]
