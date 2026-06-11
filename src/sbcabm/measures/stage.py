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
from .targets import build_acs_targets
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
        households=store.get("households") if store.has("households") else None,
        transit_skims=store.get("transit_skims") if store.has("transit_skims") else None,
        network_summary=store.get("network_summary") if store.has("network_summary") else None,
    )
    store.put("measures", measures)

    targets = _collect_targets(config, store)
    if targets is not None and len(targets):
        store.put("validation_gaps", gap_report(measures, targets))


def _collect_targets(config: Config, store: DataStore):
    """Assemble validation targets: ACS-derived (auto) + curated file targets."""
    import pandas as pd

    frames = []
    # Primary: targets built from the county ACS validation pull (PRD OD1).
    if store.has("acs_validation"):
        acs_targets = build_acs_targets(store.get("acs_validation"))
        if len(acs_targets):
            frames.append(acs_targets)

    # Secondary: curated rate targets (e.g. NHTS 2017) from a CSV.
    targets_path = (config.raw or {}).get("validation", {}).get("targets_path")
    if targets_path:
        path = Path(targets_path)
        if not path.is_absolute():
            candidate = config.config_dir / path
            path = candidate if candidate.exists() else path
        if path.exists():
            frames.append(load_targets(path))
        else:
            logger.warning("validation targets %s not found; skipping file targets", path)

    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)
