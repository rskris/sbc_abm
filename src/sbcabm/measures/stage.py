"""The ``measures`` pipeline stage.

Computes the standard measure set from the finished run and, when a validation
targets file is configured (``validation.targets_path``), the model-vs-observed
gap report.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..config import Config
from ..pipeline import DataStore
from .measures import compute_measures
from .validation import gap_report, load_targets

logger = logging.getLogger("sbcabm.measures")

_REQUIRED = ("persons", "tours", "trips", "skims")


def run_measures(config: Config, store: DataStore) -> None:
    missing = [name for name in _REQUIRED if not store.has(name)]
    if missing:
        raise KeyError(f"measures requires {missing}; run earlier stages first")

    measures = compute_measures(
        store.get("persons"),
        store.get("tours"),
        store.get("trips"),
        store.get("skims"),
        transit_skims=store.get("transit_skims") if store.has("transit_skims") else None,
        network_summary=store.get("network_summary") if store.has("network_summary") else None,
    )
    store.put("measures", measures)

    targets_path = (config.raw or {}).get("validation", {}).get("targets_path")
    if targets_path:
        path = Path(targets_path)
        if not path.is_absolute():
            candidate = config.config_dir / path
            path = candidate if candidate.exists() else path
        if path.exists():
            store.put("validation_gaps", gap_report(measures, load_targets(path)))
        else:
            logger.warning("validation targets %s not found; skipping gap report", path)
