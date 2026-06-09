"""Typed configuration for an SBC ABM run.

A run is fully described by a YAML file (see ``configs/settings.yaml``). This
module loads that file into validated, attribute-accessible dataclasses so the
rest of the code never reaches into raw dicts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RegionConfig:
    name: str
    state_fips: str
    county_fips: str
    working_crs: str = "EPSG:2229"
    geographic_crs: str = "EPSG:4326"

    @property
    def county_geoid(self) -> str:
        """5-digit state+county FIPS, e.g. '06083' for Santa Barbara County."""
        return f"{self.state_fips}{self.county_fips}"


@dataclass(frozen=True)
class PathsConfig:
    cache_dir: Path = Path("data/cache")
    output_dir: Path = Path("outputs")
    fixtures_dir: Path = Path("tests/fixtures")


@dataclass(frozen=True)
class DataConfig:
    acs_year: int = 2022
    pums_year: int = 2022
    tiger_year: int = 2022
    census_api_key: str | None = None
    allow_network: bool = True


@dataclass(frozen=True)
class ZonesConfig:
    system: str = "block_group"
    custom_taz_path: str | None = None


@dataclass(frozen=True)
class PopsynConfig:
    max_iterations: int = 100
    convergence_tolerance: float = 1e-4
    household_controls: list[str] = field(default_factory=list)
    person_controls: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    region: RegionConfig
    random_seed: int = 42
    paths: PathsConfig = field(default_factory=PathsConfig)
    data: DataConfig = field(default_factory=DataConfig)
    zones: ZonesConfig = field(default_factory=ZonesConfig)
    popsyn: PopsynConfig = field(default_factory=PopsynConfig)
    stages: list[str] = field(default_factory=list)
    # Original parsed mapping, kept for forward-compatibility / debugging.
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_file(cls, path: str | os.PathLike[str]) -> Config:
        """Load and validate configuration from a YAML file."""
        text = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(text) or {}
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        if "region" not in data:
            raise ValueError("config is missing required 'region' section")
        region = RegionConfig(**data["region"])

        paths_raw = data.get("paths", {})
        paths = PathsConfig(
            cache_dir=Path(paths_raw.get("cache_dir", "data/cache")),
            output_dir=Path(paths_raw.get("output_dir", "outputs")),
            fixtures_dir=Path(paths_raw.get("fixtures_dir", "tests/fixtures")),
        )

        data_cfg = DataConfig(**data.get("data", {}))

        # An env var, if present, overrides a null/absent key in the file.
        if data_cfg.census_api_key is None and os.environ.get("CENSUS_API_KEY"):
            data_cfg = DataConfig(
                acs_year=data_cfg.acs_year,
                pums_year=data_cfg.pums_year,
                tiger_year=data_cfg.tiger_year,
                census_api_key=os.environ["CENSUS_API_KEY"],
                allow_network=data_cfg.allow_network,
            )

        zones = ZonesConfig(**data.get("zones", {}))
        popsyn = PopsynConfig(**data.get("popsyn", {}))
        stages = list(data.get("pipeline", {}).get("stages", []))

        return cls(
            region=region,
            random_seed=int(data.get("random_seed", 42)),
            paths=paths,
            data=data_cfg,
            zones=zones,
            popsyn=popsyn,
            stages=stages,
            raw=data,
        )


def load_config(path: str | os.PathLike[str]) -> Config:
    """Convenience wrapper around :meth:`Config.from_file`."""
    return Config.from_file(path)
