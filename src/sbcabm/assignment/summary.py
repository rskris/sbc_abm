"""Measures-ready network summaries from assignment outputs (story 6.5).

Rolls link-level volumes and congested times up to per-period system totals:
vehicle-miles traveled (VMT), vehicle-hours traveled (VHT), the average speed
they imply, and the volume-weighted v/c-style congestion indicator
(congested/free-flow time ratio).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..network.graph import Network
from .static import _directed_links

logger = logging.getLogger("sbcabm.assignment.summary")


def network_summary(
    link_volumes: pd.DataFrame,
    congested_times: pd.DataFrame,
    network: Network,
) -> pd.DataFrame:
    """Per-period VMT, VHT, average speed, and mean congestion ratio."""
    links = _directed_links(network, capacity_per_lane=1.0)[
        ["from_node", "to_node"]
    ].assign(
        length_mi=_directed_lengths(network)
    )
    merged = link_volumes.merge(links, on=["from_node", "to_node"], how="left").merge(
        congested_times, on=["from_node", "to_node", "period"], how="left"
    )

    rows = []
    for period, sub in merged.groupby("period"):
        vmt = float((sub["volume"] * sub["length_mi"]).sum())
        vht = float((sub["volume"] * sub["time_min"] / 60.0).sum())
        loaded = sub[sub["volume"] > 0]
        ratio = (
            float(
                np.average(
                    loaded["time_min"] / loaded["free_flow_min"], weights=loaded["volume"]
                )
            )
            if len(loaded)
            else 1.0
        )
        rows.append(
            {
                "period": period,
                "vmt": vmt,
                "vht": vht,
                "avg_speed_mph": vmt / vht if vht > 0 else float("nan"),
                "congestion_ratio": ratio,
            }
        )
    summary = pd.DataFrame(rows)
    logger.info("network summary: %d periods, total VMT %.1f", len(summary), summary["vmt"].sum())
    return summary


def _directed_lengths(network: Network) -> np.ndarray:
    drivable = network.links[network.links["allow_drive"].astype(bool)]
    lengths = []
    for link in drivable.itertuples():
        lengths.append(float(link.length_mi))
        if not bool(getattr(link, "oneway", False)):
            lengths.append(float(link.length_mi))
    return np.asarray(lengths)
