"""Public-data ingestion for SBC ABM.

All model inputs derive from free, public sources (see
``docs/DATA_SOURCES.md``). This package fetches and caches them. Heavy
geospatial/network ingestion (TIGER, OSM, GTFS) lands in later phases; today the
Census ACS/PUMS client and the source registry are provided.
"""

from __future__ import annotations

from .sources import SOURCES, DataSource, get_source

__all__ = ["SOURCES", "DataSource", "get_source"]
