"""Assemble per-zone marginal controls from ACS detailed tables."""

from __future__ import annotations

import logging

import pandas as pd

from .specs import ControlSpec

logger = logging.getLogger("sbcabm.popsyn.marginals")


def build_controls(
    acs: pd.DataFrame,
    specs: tuple[ControlSpec, ...],
    *,
    geoid_col: str = "GEOID",
) -> pd.DataFrame:
    """Sum ACS estimate columns into one marginal control column per spec.

    Parameters
    ----------
    acs:
        ACS table with one row per zone and numeric estimate columns (``...E``),
        plus ``geoid_col`` identifying the zone.
    specs:
        Control specifications; each control's marginal is the row-wise sum of
        its ``acs_variables``.
    geoid_col:
        Column holding the zone identifier; becomes the ``zone_id`` index.

    Notes
    -----
    Variables absent from ``acs`` (e.g. a bracket missing for the configured
    vintage) are treated as zero with a warning — except the ``total_households``
    control, whose variables must all be present, since it anchors the count.
    """
    if geoid_col not in acs.columns:
        raise KeyError(f"acs is missing the geography column '{geoid_col}'")

    index = pd.Index(acs[geoid_col].astype(str), name="zone_id")
    controls = pd.DataFrame(index=index)

    for spec in specs:
        present = [c for c in spec.acs_variables if c in acs.columns]
        missing = [c for c in spec.acs_variables if c not in acs.columns]
        if missing:
            if spec.name == "total_households":
                raise KeyError(
                    f"total_households control needs {missing}, absent from acs columns"
                )
            logger.warning(
                "control '%s' is missing ACS variables %s; treating as 0",
                spec.name,
                missing,
            )
        if present:
            numeric = acs[present].apply(pd.to_numeric, errors="coerce").fillna(0.0)
            controls[spec.name] = numeric.sum(axis=1).to_numpy()
        else:
            controls[spec.name] = 0.0

    return controls
