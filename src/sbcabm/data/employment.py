"""LEHD LODES employment ingestion → zonal employment by sector.

LODES Workplace Area Characteristics (WAC) give the number of jobs at each
Census *block* by NAICS sector (columns ``CNS01``…``CNS20``) plus a total
``C000``. Travel models need jobs at the *zone* (block group) level, grouped
into a handful of land-use categories that drive destination choice (the "size
terms" of a destination-choice model: shoppers go where retail jobs are, etc.).

This module aggregates block-level WAC to block groups (the first 12 digits of
the 15-digit block GEOID) and rolls the 20 NAICS sectors into model categories.
Pure pandas — no geospatial dependencies.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("sbcabm.data.employment")

# LODES NAICS-sector columns → model employment categories (size terms).
LODES_SECTOR_GROUPS: dict[str, tuple[str, ...]] = {
    "emp_retail": ("CNS07",),
    "emp_office": ("CNS09", "CNS10", "CNS11", "CNS12", "CNS13", "CNS14", "CNS20"),
    "emp_industrial": ("CNS01", "CNS02", "CNS03", "CNS04", "CNS05", "CNS06", "CNS08"),
    "emp_education": ("CNS15",),
    "emp_health": ("CNS16",),
    "emp_service": ("CNS17", "CNS18", "CNS19"),
}


def aggregate_employment(
    wac: pd.DataFrame,
    *,
    geocode_col: str = "w_geocode",
    total_col: str = "C000",
) -> pd.DataFrame:
    """Aggregate block-level LODES WAC to block-group employment by category.

    Parameters
    ----------
    wac:
        LODES WAC table: one row per workplace block with ``geocode_col`` (a
        15-digit block GEOID), a ``total_col`` of all jobs, and ``CNS*`` sector
        columns.
    geocode_col, total_col:
        Column names for the block id and total jobs.

    Returns
    -------
    DataFrame indexed by 12-digit block-group ``zone_id`` with ``emp_total`` and
    one column per model employment category. Sector columns absent from the
    input contribute zero.
    """
    if geocode_col not in wac.columns:
        raise KeyError(f"LODES table is missing block id column '{geocode_col}'")
    if total_col not in wac.columns:
        raise KeyError(f"LODES table is missing total jobs column '{total_col}'")

    block_group = wac[geocode_col].astype(str).str.zfill(15).str[:12]

    sector_cols = sorted({c for cols in LODES_SECTOR_GROUPS.values() for c in cols})
    keep = [total_col, *[c for c in sector_cols if c in wac.columns]]
    numeric = wac[keep].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    numeric.insert(0, "zone_id", block_group.to_numpy())

    grouped = numeric.groupby("zone_id").sum()

    out = pd.DataFrame(index=grouped.index)
    out["emp_total"] = grouped[total_col]
    for category, cols in LODES_SECTOR_GROUPS.items():
        present = [c for c in cols if c in grouped.columns]
        out[category] = grouped[present].sum(axis=1) if present else 0.0

    logger.info(
        "aggregated LODES: %d blocks → %d block groups (%d total jobs)",
        len(wac),
        len(out),
        int(out["emp_total"].sum()),
    )
    return out
