"""Tests for story 7.5 tooling: preflight, strict mode, live config."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sbcabm.config import load_config
from sbcabm.data.preflight import (
    check_hosts,
    required_hosts,
    run_preflight,
    verify_acs_scheme,
)
from sbcabm.pipeline import build_pipeline
from sbcabm.popsyn.specs import acs_variables, all_control_specs

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_CONFIG = REPO_ROOT / "configs" / "live.yaml"


def _ok_getter(url):
    return SimpleNamespace(status_code=200, text="<html>ok</html>")


def _blocked_getter(url):
    return SimpleNamespace(status_code=403, text="Host not in allowlist")


def _full_metadata(url):
    """Fake Census metadata containing every variable the specs need."""
    variables = dict.fromkeys(
        [*acs_variables(all_control_specs()), "SERIALNO", "NP", "HINCP",
         "WGTP", "SPORDER", "AGEP", "PWGTP"],
        {},
    )
    return {"variables": variables}


def test_required_hosts_cover_all_sources():
    hosts = required_hosts()
    assert "api.census.gov" in hosts
    assert "www2.census.gov" in hosts
    assert "www.sbmtd.gov" in hosts  # registry host matches its URL


def test_check_hosts_reachable_and_blocked():
    ok = check_hosts(["api.census.gov"], getter=_ok_getter)
    assert ok.iloc[0]["reachable"]

    blocked = check_hosts(["api.census.gov"], getter=_blocked_getter)
    assert not blocked.iloc[0]["reachable"]
    assert "network policy" in blocked.iloc[0]["detail"]


def test_check_hosts_connection_error():
    def boom(url):
        raise ConnectionError("no route to host")

    report = check_hosts(["api.census.gov"], getter=boom)
    assert not report.iloc[0]["reachable"]
    assert "ConnectionError" in report.iloc[0]["detail"]


def test_verify_acs_scheme_all_found():
    report = verify_acs_scheme(2022, fetch_json=_full_metadata)
    assert report["found"].all()
    assert set(report["dataset"]) == {"acs", "pums"}


def test_verify_acs_scheme_detects_missing():
    def partial(url):
        meta = _full_metadata(url)
        meta["variables"].pop("B11016_001E", None)
        return meta

    report = verify_acs_scheme(2022, fetch_json=partial)
    missing = report[~report["found"]]
    assert list(missing["variable"]) == ["B11016_001E"]


def test_run_preflight_pass_and_fail():
    config = load_config(LIVE_CONFIG)
    report, ok = run_preflight(config, getter=_ok_getter, fetch_json=_full_metadata)
    assert ok
    assert (report[report["check"] == "host"]["reachable"]).all()

    report, ok = run_preflight(config, getter=_blocked_getter)
    assert not ok
    # Scheme check is reported as skipped when the API host is unreachable.
    skipped = report[report["check"] == "variable"]
    assert not skipped["reachable"].any()


def test_live_config_loads_with_strict():
    config = load_config(LIVE_CONFIG)
    assert config.data.strict
    assert config.data.allow_network
    assert config.region.county_geoid == "06083"
    assert config.stages[-1] == "measures"


def test_strict_mode_refuses_fixture_fallback():
    config = load_config(LIVE_CONFIG)
    # Force the census path to fail (network blocked here) while strict is on.
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    pipeline = build_pipeline(config)
    with pytest.raises(RuntimeError, match="refusing fixture fallback"):
        pipeline.run(["ingest"])
