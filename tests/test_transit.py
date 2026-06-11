"""Tests for GTFS transit feed ingestion."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from sbcabm.data.transit import load_gtfs, summarize_service

REPO_ROOT = Path(__file__).resolve().parents[1]
GTFS_DIR = REPO_ROOT / "tests" / "fixtures" / "gtfs"


def test_load_gtfs_from_directory():
    gtfs = load_gtfs(GTFS_DIR)
    assert set(gtfs) == {"stops", "routes", "trips", "stop_times"}
    assert len(gtfs["stops"]) == 2
    assert list(gtfs["routes"]["route_id"]) == ["R1"]
    # IDs are coerced to strings for safe joins.
    assert all(isinstance(v, str) for v in gtfs["stop_times"]["stop_id"])


def test_load_gtfs_from_zip(tmp_path):
    archive = tmp_path / "feed.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for name in ("stops", "routes", "trips", "stop_times"):
            zf.write(GTFS_DIR / f"{name}.txt", arcname=f"{name}.txt")
    gtfs = load_gtfs(archive)
    assert len(gtfs["stops"]) == 2


def test_summarize_service():
    summary = summarize_service(load_gtfs(GTFS_DIR))
    row = summary.iloc[0]
    assert row["n_routes"] == 1
    assert row["n_stops"] == 2
    assert row["n_trips"] == 1
    assert row["n_stop_times"] == 2


def test_load_gtfs_rejects_bad_path(tmp_path):
    with pytest.raises(ValueError, match="directory or .zip"):
        load_gtfs(tmp_path / "feed.txt")
