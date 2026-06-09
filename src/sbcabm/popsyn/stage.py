"""Pipeline stage that runs population synthesis.

Reads four tables from the data store — ``seed_households``, ``seed_persons``,
``incidence`` and ``controls`` — and writes ``households``, ``persons`` and
``popsyn_diagnostics``. If the inputs are absent (e.g. an offline run where the
ingest/zones stages have not produced real data), it loads the bundled fixtures
so the mechanics stay exercisable.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ..config import Config
from ..pipeline import DataStore
from .synthesizer import synthesize

logger = logging.getLogger("sbcabm.popsyn")

_REQUIRED = ("seed_households", "seed_persons", "incidence", "controls")
_SEED_HH_ID = "seed_household_id"


def run_popsyn(config: Config, store: DataStore) -> None:
    _ensure_inputs(config, store)

    seed_households = store.get("seed_households")
    seed_persons = store.get("seed_persons")
    incidence = store.get("incidence")
    controls = store.get("controls")

    total_control = (
        "total_households" if "total_households" in controls.columns else None
    )

    result = synthesize(
        seed_households=seed_households,
        seed_persons=seed_persons,
        incidence=incidence,
        controls=controls,
        total_households_control=total_control,
        hh_id_col=_SEED_HH_ID,
        person_hh_id_col=_SEED_HH_ID,
        seed=config.random_seed,
        max_iterations=config.popsyn.max_iterations,
        tolerance=config.popsyn.convergence_tolerance,
    )

    store.put("households", result.households)
    store.put("persons", result.persons)
    store.put("popsyn_diagnostics", result.diagnostics)

    converged = int(result.diagnostics["balance_converged"].sum())
    logger.info(
        "synthesized %d households / %d persons across %d zones (%d/%d converged)",
        result.n_households,
        result.n_persons,
        len(result.diagnostics),
        converged,
        len(result.diagnostics),
    )


def _ensure_inputs(config: Config, store: DataStore) -> None:
    """Populate any missing input tables from bundled fixtures."""
    missing = [name for name in _REQUIRED if not store.has(name)]
    if not missing:
        return

    fixtures = Path(config.paths.fixtures_dir) / "popsyn"
    logger.warning(
        "popsyn inputs %s not in store; loading fixtures from %s", missing, fixtures
    )
    for name in missing:
        path = fixtures / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"required table '{name}' is absent and no fixture exists at {path}"
            )
        store.put(name, _load_fixture(name, path))


def _load_fixture(name: str, path: Path) -> pd.DataFrame:
    """Load a fixture CSV, indexing seed/incidence tables by seed household id."""
    df = pd.read_csv(path)
    if name in ("seed_households", "incidence") and _SEED_HH_ID in df.columns:
        df = df.set_index(_SEED_HH_ID)
    if name == "controls" and "zone_id" in df.columns:
        df = df.set_index("zone_id")
    return df
