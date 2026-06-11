"""Per-tour level-of-service (LOS): look up skims for each tour's O-D.

Assembles the mode attributes the mode-choice utility needs — auto/walk/bike
time and distance from the road skims, transit time from the RAPTOR transit
skims — plus simple monetary costs (auto operating cost per mile; a flat transit
fare). Missing skim values mean the mode is unavailable at that O-D.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Mode attribute columns produced for each tour.
LOS_COLUMNS = (
    "auto_time",
    "auto_dist",
    "walk_time",
    "bike_time",
    "transit_time",
    "auto_cost",
    "transit_cost",
)


def build_mode_los(
    tours: pd.DataFrame,
    skims: pd.DataFrame,
    transit_skims: pd.DataFrame | None = None,
    *,
    origin_col: str = "home_zone",
    dest_col: str = "dest_zone",
    auto_cost_per_mile: float = 0.20,
    transit_fare: float = 1.75,
) -> pd.DataFrame:
    """Return ``tours``-aligned LOS columns (NaN where a mode is unavailable)."""
    keys = list(zip(tours[origin_col], tours[dest_col], strict=True))
    los = pd.DataFrame(index=tours.index)

    auto_time = _lookup(skims, "auto", "time_min")
    auto_dist = _lookup(skims, "auto", "dist_mi")
    walk_time = _lookup(skims, "walk", "time_min")
    bike_time = _lookup(skims, "bike", "time_min")
    transit_time = _transit_lookup(transit_skims)

    los["auto_time"] = [auto_time.get(k, np.nan) for k in keys]
    los["auto_dist"] = [auto_dist.get(k, np.nan) for k in keys]
    los["walk_time"] = [walk_time.get(k, np.nan) for k in keys]
    los["bike_time"] = [bike_time.get(k, np.nan) for k in keys]
    los["transit_time"] = [transit_time.get(k, np.nan) for k in keys]

    los["auto_cost"] = los["auto_dist"] * auto_cost_per_mile
    los["transit_cost"] = np.where(los["transit_time"].notna(), transit_fare, np.nan)
    return los


def _lookup(skims: pd.DataFrame, mode: str, value: str) -> dict:
    sub = skims[skims["mode"] == mode]
    return {
        (o, d): v
        for o, d, v in zip(sub["origin_zone"], sub["dest_zone"], sub[value], strict=True)
    }


def _transit_lookup(transit_skims: pd.DataFrame | None) -> dict:
    if transit_skims is None or transit_skims.empty:
        return {}
    return {
        (o, d): v
        for o, d, v in zip(
            transit_skims["origin_zone"],
            transit_skims["dest_zone"],
            transit_skims["total_time_min"],
            strict=True,
        )
    }
