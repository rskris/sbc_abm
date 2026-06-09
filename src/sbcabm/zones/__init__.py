"""Zone system for SBC ABM.

The zone system ties model zones (TAZs — by default Census block groups) to
their identifiers, centroids and zonal attributes (households, population,
employment, area). It is the spatial index every downstream model joins to.

The geometry-backed loaders (TIGER ingestion, reprojection, adjacency) arrive in
Phase 1 and depend on the optional ``geo`` extra; this module currently provides
the attribute-table backbone that works without geopandas.
"""

from __future__ import annotations

from .zone_system import ZoneSystem

__all__ = ["ZoneSystem"]
