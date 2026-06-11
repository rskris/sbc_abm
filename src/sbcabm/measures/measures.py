"""Standard run measures in tidy long form (story 7.1).

Every measure is one row ``(measure, segment, value)`` so downstream tooling
(validation gaps, scenario diffs) can treat them uniformly:

* ``trips_total`` / ``trips_per_person`` — segment ``all``;
* ``mode_share_trip`` / ``mode_share_tour`` — one segment per mode (shares sum
  to 1 within each measure);
* ``vmt_person_auto`` — person-miles over auto-mode trips, from skim distances;
* ``transit_boardings`` — count of transit trips;
* ``avg_travel_time`` — minutes, one segment per trip purpose, using each
  trip's own mode LOS;
* ``network_vmt`` / ``network_vht`` — one segment per period, from the
  assignment's network summary when present.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("sbcabm.measures")

AUTO_MODES = ("drive_alone", "shared_ride")
MEASURE_COLUMNS = ("measure", "segment", "value")


def compute_measures(
    persons: pd.DataFrame,
    tours: pd.DataFrame,
    trips: pd.DataFrame,
    skims: pd.DataFrame,
    *,
    households: pd.DataFrame | None = None,
    transit_skims: pd.DataFrame | None = None,
    network_summary: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute the standard measure set for a finished run."""
    from ..assignment.plans import make_time_lookup

    rows: list[tuple[str, str, float]] = []

    rows.append(("trips_total", "all", float(len(trips))))
    if len(persons):
        rows.append(("trips_per_person", "all", len(trips) / len(persons)))

    commute = trips[trips["purpose"] == "work"] if "purpose" in trips.columns else trips.iloc[0:0]
    for measure, frame, col in (
        ("mode_share_trip", trips, "mode"),
        ("mode_share_tour", tours, "tour_mode"),
        ("mode_share_commute", commute, "mode"),
    ):
        if col in frame.columns and len(frame):
            shares = frame[col].value_counts(normalize=True)
            rows.extend((measure, mode, float(share)) for mode, share in shares.items())

    if households is not None and "auto_ownership" in households.columns and len(households):
        shares = households["auto_ownership"].value_counts(normalize=True)
        rows.extend(
            ("auto_ownership_share", category, float(share))
            for category, share in shares.items()
        )

    dist = {
        (o, d): v
        for o, d, v in zip(
            skims.query("mode == 'auto'")["origin_zone"],
            skims.query("mode == 'auto'")["dest_zone"],
            skims.query("mode == 'auto'")["dist_mi"],
            strict=True,
        )
    }
    auto_trips = trips[trips["mode"].isin(AUTO_MODES)]
    vmt = sum(
        dist.get((t.origin_zone, t.dest_zone), 0.0) for t in auto_trips.itertuples()
    )
    rows.append(("vmt_person_auto", "all", float(vmt)))

    rows.append(
        ("transit_boardings", "all", float((trips["mode"] == "walk_transit").sum()))
    )

    lookup = make_time_lookup(skims, transit_skims)
    times = pd.Series(
        [lookup(t.origin_zone, t.dest_zone, t.mode) for t in trips.itertuples()],
        index=trips.index,
    )
    for purpose, group in trips.groupby("purpose"):
        rows.append(("avg_travel_time", str(purpose), float(times.loc[group.index].mean())))

    if network_summary is not None and len(network_summary):
        for row in network_summary.itertuples():
            rows.append(("network_vmt", row.period, float(row.vmt)))
            rows.append(("network_vht", row.period, float(row.vht)))

    measures = pd.DataFrame(rows, columns=list(MEASURE_COLUMNS))
    logger.info("computed %d measures", len(measures))
    return measures
