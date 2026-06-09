"""Stage-based pipeline orchestrator.

Stages never call one another. Each stage reads named tables from a shared
:class:`DataStore` and writes named tables back. The orchestrator runs an
ordered list of stages, checkpointing the store between them so a run can be
resumed or a single stage debugged in isolation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

from .config import Config

logger = logging.getLogger("sbcabm.pipeline")


class DataStore:
    """An in-memory, named collection of tables shared across stages.

    Kept deliberately small: a dict of ``name -> DataFrame`` plus convenience
    accessors. Checkpointing to disk lives in the orchestrator.
    """

    def __init__(self) -> None:
        self._tables: dict[str, pd.DataFrame] = {}

    def put(self, name: str, table: pd.DataFrame) -> None:
        self._tables[name] = table

    def get(self, name: str) -> pd.DataFrame:
        if name not in self._tables:
            raise KeyError(
                f"table '{name}' not in data store; available: {sorted(self._tables)}"
            )
        return self._tables[name]

    def has(self, name: str) -> bool:
        return name in self._tables

    def names(self) -> list[str]:
        return sorted(self._tables)


class Stage(Protocol):
    """A pipeline stage: a callable that mutates the data store."""

    name: str

    def run(self, config: Config, store: DataStore) -> None: ...


@dataclass
class FunctionStage:
    """Adapts a plain function into a :class:`Stage`."""

    name: str
    fn: Callable[[Config, DataStore], None]
    description: str = ""

    def run(self, config: Config, store: DataStore) -> None:
        self.fn(config, store)


@dataclass
class StageRegistry:
    """Maps stage names (as they appear in config) to implementations."""

    _stages: dict[str, Stage] = field(default_factory=dict)

    def register(self, stage: Stage) -> None:
        self._stages[stage.name] = stage

    def get(self, name: str) -> Stage | None:
        return self._stages.get(name)

    def names(self) -> list[str]:
        return list(self._stages)


def build_default_registry() -> StageRegistry:
    """Register the stages that exist today.

    Stages named in config but absent here are reported as "not yet
    implemented" and skipped, so a full pipeline config is documentation of
    intent without breaking partial runs.
    """
    registry = StageRegistry()

    # Imported lazily to keep optional/heavy deps out of the import path.
    from .data.ingest import run_ingest
    from .popsyn.stage import run_popsyn
    from .zones.stage import run_zones

    registry.register(
        FunctionStage(
            name="ingest",
            fn=run_ingest,
            description="Fetch/cache ACS marginals and PUMS seed records (fixture fallback).",
        )
    )
    registry.register(
        FunctionStage(
            name="zones",
            fn=run_zones,
            description="Build the model zone table from ingested block groups.",
        )
    )
    registry.register(
        FunctionStage(
            name="popsyn",
            fn=run_popsyn,
            description="Synthesize households and persons from controls + seed.",
        )
    )
    return registry


@dataclass
class Pipeline:
    config: Config
    registry: StageRegistry
    store: DataStore = field(default_factory=DataStore)

    def run(self, stages: list[str] | None = None) -> DataStore:
        """Run the requested stages (default: those listed in the config)."""
        requested = stages if stages is not None else self.config.stages
        for name in requested:
            stage = self.registry.get(name)
            if stage is None:
                logger.warning("stage '%s' is not yet implemented — skipping", name)
                continue
            logger.info("running stage '%s'", name)
            stage.run(self.config, self.store)
            logger.info("stage '%s' complete; tables: %s", name, self.store.names())
        return self.store


def build_pipeline(config: Config) -> Pipeline:
    return Pipeline(config=config, registry=build_default_registry())
