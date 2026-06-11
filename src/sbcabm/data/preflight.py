"""Preflight checks for a live-data run (story 7.5).

Before committing to a real ingest, verify that:

1. every public-data **host** the pipeline needs is reachable from this
   environment (Claude-style sandboxes and corporate proxies commonly return
   ``403`` with an "allowlist" body for blocked hosts), and
2. the **ACS/PUMS variable scheme** in ``popsyn/specs.py`` exists in the live
   Census API for the configured vintage — the scheme was authored against
   documented table structures and must be confirmed before production use.

Both checks accept injectable fetchers so they are fully testable offline.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import pandas as pd
import requests

from ..config import Config
from ..popsyn.specs import (
    PUMS_HOUSEHOLD_VARIABLES,
    PUMS_PERSON_VARIABLES,
    acs_variables,
    all_control_specs,
)
from .sources import SOURCES

logger = logging.getLogger("sbcabm.data.preflight")

_TIMEOUT = 10


def required_hosts() -> list[str]:
    """Every distinct host in the public-data source registry."""
    return sorted({source.host for source in SOURCES.values()})


def check_hosts(
    hosts: list[str] | None = None,
    *,
    getter: Callable | None = None,
) -> pd.DataFrame:
    """Probe each host; return ``host``, ``reachable``, ``detail`` rows."""
    getter = getter or (lambda url: requests.get(url, timeout=_TIMEOUT))
    rows = []
    for host in hosts if hosts is not None else required_hosts():
        try:
            response = getter(f"https://{host}/")
            body = (getattr(response, "text", "") or "")[:200]
            if "allowlist" in body.lower():
                rows.append((host, False, "blocked by environment network policy"))
            else:
                rows.append((host, True, f"http {response.status_code}"))
        except Exception as exc:  # noqa: BLE001 — any transport failure is "unreachable"
            rows.append((host, False, f"{type(exc).__name__}: {exc}"))
    return pd.DataFrame(rows, columns=["host", "reachable", "detail"])


def verify_acs_scheme(
    year: int,
    *,
    fetch_json: Callable[[str], dict] | None = None,
) -> pd.DataFrame:
    """Check every spec variable against the live Census variable metadata.

    Queries ``…/acs/acs5/variables.json`` and ``…/acs/acs5/pums/variables.json``
    for the vintage and reports each required variable as found or missing.
    """
    fetch_json = fetch_json or _fetch_json

    acs_meta = fetch_json(f"https://api.census.gov/data/{year}/acs/acs5/variables.json")
    pums_meta = fetch_json(f"https://api.census.gov/data/{year}/acs/acs5/pums/variables.json")
    acs_known = set(acs_meta.get("variables", {}))
    pums_known = set(pums_meta.get("variables", {}))

    rows = [
        ("acs", var, var in acs_known)
        for var in acs_variables(all_control_specs())
    ]
    pums_vars = dict.fromkeys((*PUMS_HOUSEHOLD_VARIABLES, *PUMS_PERSON_VARIABLES))
    rows += [("pums", var, var in pums_known) for var in pums_vars]

    report = pd.DataFrame(rows, columns=["dataset", "variable", "found"])
    missing = report[~report["found"]]
    if len(missing):
        logger.warning(
            "variable scheme: %d of %d variables missing for vintage %d",
            len(missing), len(report), year,
        )
    else:
        logger.info("variable scheme: all %d variables found for vintage %d", len(report), year)
    return report


def _fetch_json(url: str) -> dict:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def run_preflight(config: Config, *, getter=None, fetch_json=None) -> tuple[pd.DataFrame, bool]:
    """Full preflight: host reachability plus (when possible) scheme verification.

    Returns a combined report and an overall pass/fail flag. The scheme check
    runs only when ``api.census.gov`` is reachable; otherwise it is reported as
    skipped (and the preflight fails, since a live run cannot proceed).
    """
    hosts = check_hosts(getter=getter)
    ok = bool(hosts["reachable"].all())

    frames = [hosts.assign(check="host")]
    census_ok = bool(
        hosts.loc[hosts["host"] == "api.census.gov", "reachable"].any()
    )
    if census_ok:
        scheme = verify_acs_scheme(config.data.acs_year, fetch_json=fetch_json)
        ok = ok and bool(scheme["found"].all())
        frames.append(
            scheme.rename(columns={"variable": "host", "found": "reachable"})
            .assign(check="variable", detail=lambda df: df.pop("dataset"))
        )
    else:
        frames.append(
            pd.DataFrame(
                [("variable scheme", False, "skipped: api.census.gov unreachable", "variable")],
                columns=["host", "reachable", "detail", "check"],
            )
        )
        ok = False
    report = pd.concat(frames, ignore_index=True)[["check", "host", "reachable", "detail"]]
    return report, ok
