"""US Census ACS / PUMS ingestion client.

Fetches ACS detailed tables (marginal control totals) and PUMS micro-data (seed
households/persons) from the Census API, caching every response on disk so a
given (query, vintage) is downloaded once. In network-restricted environments
the request will fail clearly; callers should fall back to fixtures.

The Census API returns JSON as a list of rows where the first row is the header.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pandas as pd
import requests

from .sources import get_source

logger = logging.getLogger("sbcabm.data.census")

_DEFAULT_TIMEOUT = 30


class CensusClient:
    """Thin, cached client over the Census data API."""

    def __init__(
        self,
        *,
        year: int = 2022,
        api_key: str | None = None,
        cache_dir: str | Path = "data/cache",
        allow_network: bool = True,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self.year = year
        self.api_key = api_key
        self.cache_dir = Path(cache_dir) / "census"
        self.allow_network = allow_network
        self.timeout = timeout

    # -- low level ---------------------------------------------------------

    def _cache_path(self, base_url: str, params: dict[str, str]) -> Path:
        payload = json.dumps({"url": base_url, "params": params}, sort_keys=True)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return self.cache_dir / f"{digest}.json"

    def _get(self, base_url: str, params: dict[str, str]) -> list[list[str]]:
        cache_path = self._cache_path(base_url, params)
        if cache_path.exists():
            logger.debug("census cache hit: %s", cache_path)
            return json.loads(cache_path.read_text(encoding="utf-8"))

        if not self.allow_network:
            raise RuntimeError(
                "network access disabled and no cached response for this query; "
                f"populate {cache_path} from an online run or use fixtures"
            )

        query = dict(params)
        if self.api_key:
            query["key"] = self.api_key

        logger.info("census request: %s %s", base_url, {k: params[k] for k in params})
        response = requests.get(base_url, params=query, timeout=self.timeout)
        response.raise_for_status()
        rows = response.json()

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(rows), encoding="utf-8")
        return rows

    @staticmethod
    def _to_frame(rows: list[list[str]]) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame()
        header, *data = rows
        return pd.DataFrame(data, columns=header)

    # -- ACS detailed tables ----------------------------------------------

    def fetch_acs(
        self,
        variables: list[str],
        *,
        for_clause: str,
        in_clause: str | None = None,
    ) -> pd.DataFrame:
        """Fetch ACS 5-year variables for a geography.

        ``for_clause`` / ``in_clause`` follow Census API geography syntax, e.g.
        ``for_clause='block group:*'``, ``in_clause='state:06 county:083'``.
        Estimate columns (``...E``) are returned as numeric.
        """
        source = get_source("acs5")
        base_url = source.url(year=self.year)
        params: dict[str, str] = {"get": ",".join(variables), "for": for_clause}
        if in_clause:
            params["in"] = in_clause

        frame = self._to_frame(self._get(base_url, params))
        for col in frame.columns:
            if col.endswith("E"):  # ACS estimate columns
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
        return frame

    def block_group_acs(
        self, variables: list[str], *, state_fips: str, county_fips: str
    ) -> pd.DataFrame:
        """Convenience: ACS variables for every block group in a county.

        Adds a ``GEOID`` column (12-digit block-group identifier) for joins.
        """
        frame = self.fetch_acs(
            variables,
            for_clause="block group:*",
            in_clause=f"state:{state_fips} county:{county_fips} tract:*",
        )
        if {"state", "county", "tract", "block group"}.issubset(frame.columns):
            frame["GEOID"] = (
                frame["state"] + frame["county"] + frame["tract"] + frame["block group"]
            )
        return frame

    # -- PUMS micro-data ---------------------------------------------------

    def fetch_pums(
        self,
        variables: list[str],
        *,
        state_fips: str,
        pumas: list[str] | None = None,
    ) -> pd.DataFrame:
        """Fetch PUMS records for a state, optionally limited to given PUMAs.

        Returns one row per PUMS person/household record (depending on the
        variables requested). ``SERIALNO`` links persons to households.
        """
        source = get_source("pums")
        base_url = source.url(year=self.year)
        params: dict[str, str] = {
            "get": ",".join(variables),
            "for": f"state:{state_fips}",
        }
        frame = self._to_frame(self._get(base_url, params))
        if pumas is not None and "PUMA" in frame.columns:
            frame = frame[frame["PUMA"].isin(pumas)].reset_index(drop=True)
        return frame
