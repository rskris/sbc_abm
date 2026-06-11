"""Tests for story 6.4 — co-evolutionary replanning."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sbcabm.config import load_config
from sbcabm.pipeline import build_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "configs" / "settings.yaml"


def _pipeline_after_demand():
    config = load_config(CONFIG)
    object.__setattr__(config.paths, "fixtures_dir", REPO_ROOT / "tests" / "fixtures")
    object.__setattr__(config.data, "allow_network", False)
    pipeline = build_pipeline(config)
    pipeline.run()  # full default pipeline provides the prerequisites
    return pipeline


def test_replanning_history_and_monotone_best_score():
    pipeline = _pipeline_after_demand()
    pipeline.run(["replanning"])
    history = pipeline.store.get("replanning_history")

    assert len(history) == 4  # configured iterations
    assert {"iteration", "avg_executed_score", "avg_best_score", "n_replanned"}.issubset(
        history.columns
    )
    # Memories only absorb and keep the best → average best score never drops.
    best = history["avg_best_score"].to_numpy()
    assert np.all(np.diff(best) >= -1e-9)
    # Innovation actually happened after the first iteration.
    assert history["n_replanned"].iloc[1:].sum() > 0


def test_replanning_updates_tours_and_trips():
    pipeline = _pipeline_after_demand()
    n_tours_before = len(pipeline.store.get("tours"))
    persons_before = set(pipeline.store.get("tours")["person_id"].unique())

    pipeline.run(["replanning"])
    tours = pipeline.store.get("tours")
    trips = pipeline.store.get("trips")

    # Same agents, same number of tours — only TOD/mode strategies changed.
    assert len(tours) == n_tours_before
    assert set(tours["person_id"].unique()) == persons_before
    # Final trips correspond to the final tours (2 legs per tour: no stops).
    assert len(trips) == 2 * len(tours)
    assert (trips["mode"] == trips["tour_id"].map(tours.set_index("tour_id")["tour_mode"])).all()


def test_replanning_reproducible():
    a = _pipeline_after_demand()
    a.run(["replanning"])
    b = _pipeline_after_demand()
    b.run(["replanning"])
    pd.testing.assert_frame_equal(
        a.store.get("replanning_history"), b.store.get("replanning_history")
    )


def test_replanning_requires_upstream():
    config = load_config(CONFIG)
    pipeline = build_pipeline(config)
    with pytest.raises(KeyError, match="replanning requires"):
        pipeline.run(["replanning"])
