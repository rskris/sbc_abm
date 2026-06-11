# Epic 2 — Networks & skims

**Status: Done** · Delivers FR4–FR5.
Goal: the level-of-service matrices that are the demand↔supply contract.

## Stories

### 2.1 Multimodal network graph — Done
`Network` over tidy node/link tables; mode-filtered digraphs (per-link speeds
for auto, constant for walk/bike); nearest-node lookup; centroid connectors.
*Evidence:* `src/sbcabm/network/{graph,connectors}.py`; `tests/test_network.py`.

### 2.2 OSM build with fixture fallback — Done
osmnx (lazy, `osm` extra) → node/link tables with per-class speeds and active-
mode permissions; `network` stage falls back to fixtures offline.
*Evidence:* `src/sbcabm/network/{build,stage}.py`.

### 2.3 Road skims — Done
Free-flow auto/walk/bike skims by Dijkstra from every connector, long-form by
mode and period, access/egress legs included; intrazonals fall out naturally.
*Evidence:* `src/sbcabm/skims/skims.py`; `tests/test_skims.py`.

### 2.4 GTFS ingestion — Done
Core GTFS tables from a directory or zip, string-coerced ids, service summary.
*Evidence:* `src/sbcabm/data/transit.py`; `tests/test_transit.py`.

### 2.5 RAPTOR transit skims — Done
Timetable (stop-sequence patterns + footpath transfers); round-based
earliest-arrival RAPTOR; zone-to-zone skims decomposed into
access/IVT/wait/transfer-walk/egress + transfer count, departure-time aware.
*Evidence:* `src/sbcabm/skims/transit.py`; `tests/test_transit_skims.py`.

## Carry-forward

- Congested time-of-day skims belong to Epic 6 (feedback loop), by design.
