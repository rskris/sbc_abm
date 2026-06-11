"""Skims — zone-to-zone level-of-service matrices.

Skims (travel time, distance) by mode and time period are the contract between
the demand models (which read them to choose destinations and modes) and the
supply side (which produces them by loading travelers onto the network). This
package computes free-flow auto / walk / bike skims by shortest path over the
:class:`~sbcabm.network.graph.Network`; congested skims arrive with assignment.
"""

from __future__ import annotations

from .skims import DEFAULT_MODES, SkimMode, compute_skims
from .transit import Timetable, build_timetable, compute_transit_skims, raptor

__all__ = [
    "DEFAULT_MODES",
    "SkimMode",
    "Timetable",
    "build_timetable",
    "compute_skims",
    "compute_transit_skims",
    "raptor",
]
