"""The :class:`ZoneSystem` — model zones and their attributes.

Deliberately storage-agnostic: a zones table indexed by ``zone_id`` with
attribute columns, plus optional centroid coordinates. Geometry-aware
construction from TIGER shapefiles is layered on in Phase 1 via the ``geo``
extra without changing this interface.
"""

from __future__ import annotations

import pandas as pd


class ZoneSystem:
    """A collection of model zones keyed by ``zone_id``."""

    REQUIRED_COLUMNS = ("zone_id",)

    def __init__(self, zones: pd.DataFrame) -> None:
        missing = [c for c in self.REQUIRED_COLUMNS if c not in zones.columns]
        if missing:
            raise ValueError(f"zones table is missing required columns: {missing}")
        if zones["zone_id"].duplicated().any():
            raise ValueError("zone_id values must be unique")
        self.zones = zones.set_index("zone_id", drop=False)

    def __len__(self) -> int:
        return len(self.zones)

    @property
    def ids(self) -> list:
        return self.zones["zone_id"].tolist()

    def attribute(self, name: str) -> pd.Series:
        if name not in self.zones.columns:
            raise KeyError(
                f"no zone attribute '{name}'; available: {list(self.zones.columns)}"
            )
        return self.zones[name]

    def has_centroids(self) -> bool:
        return {"centroid_x", "centroid_y"}.issubset(self.zones.columns)

    @classmethod
    def from_frame(cls, zones: pd.DataFrame) -> ZoneSystem:
        return cls(zones)

    @classmethod
    def from_csv(cls, path: str) -> ZoneSystem:
        return cls(pd.read_csv(path))
