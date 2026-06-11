"""Network assignment — the supply side's loading step.

Takes the demand pipeline's trip list and loads it onto the network, producing
link volumes and congested travel times. This package starts with classic
**static assignment** (all-or-nothing shortest paths averaged by MSA, with BPR
volume-delay); the MATSim-style dynamic mobsim and co-evolutionary replanning
build on it in later stories (6.3–6.4).
"""

from __future__ import annotations

from .static import AssignmentResult, assign_static

__all__ = ["AssignmentResult", "assign_static"]
