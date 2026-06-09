"""Tests for the discrete-choice engine: utilities, MNL, simulation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sbcabm.choice import (
    evaluate_utilities,
    load_spec,
    mnl_probabilities,
    mnl_simulate,
    simulate_choices,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
AUTO_SPEC = REPO_ROOT / "configs" / "specs" / "auto_ownership.csv"


def _spec() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "expression": ["@1", "income_k", "@(size > 2)"],
            "low": [0.0, 0.0, 0.0],
            "high": [-1.0, 0.05, 0.8],
        }
    )


def test_evaluate_utilities_constant_column_and_expression():
    choosers = pd.DataFrame({"income_k": [20.0, 100.0], "size": [1, 4]})
    utils = evaluate_utilities(choosers, _spec())
    # low is the base (all-zero) alternative.
    assert (utils["low"] == 0.0).all()
    # high: -1 + 0.05*income + 0.8*(size>2)
    assert utils["high"].iloc[0] == pytest.approx(-1 + 0.05 * 20 + 0.0)
    assert utils["high"].iloc[1] == pytest.approx(-1 + 0.05 * 100 + 0.8)


def test_mnl_probabilities_sum_to_one():
    utils = pd.DataFrame({"a": [0.0, 1.0], "b": [0.0, -1.0]})
    probs = mnl_probabilities(utils)
    np.testing.assert_allclose(probs.sum(axis=1), 1.0)
    # Equal utilities → equal probability.
    assert probs.iloc[0]["a"] == pytest.approx(0.5)
    # Higher utility → higher probability.
    assert probs.iloc[1]["a"] > probs.iloc[1]["b"]


def test_mnl_availability_zeros_unavailable():
    utils = pd.DataFrame({"a": [1.0], "b": [1.0]})
    avail = pd.DataFrame({"a": [True], "b": [False]})
    probs = mnl_probabilities(utils, availability=avail)
    assert probs.iloc[0]["a"] == pytest.approx(1.0)
    assert probs.iloc[0]["b"] == pytest.approx(0.0)


def test_no_available_alternative_is_nan():
    utils = pd.DataFrame({"a": [1.0], "b": [1.0]})
    avail = pd.DataFrame({"a": [False], "b": [False]})
    probs = mnl_probabilities(utils, availability=avail)
    assert probs.iloc[0].isna().all()


def test_simulate_choices_is_deterministic_given_rng():
    probs = pd.DataFrame({"a": [0.5, 0.9], "b": [0.5, 0.1]})
    a = simulate_choices(probs, rng=np.random.default_rng(0))
    b = simulate_choices(probs, rng=np.random.default_rng(0))
    pd.testing.assert_series_equal(a, b)
    assert set(a.unique()).issubset({"a", "b"})


def test_simulate_choices_matches_probabilities_in_expectation():
    n = 20000
    probs = pd.DataFrame({"a": [0.7] * n, "b": [0.3] * n})
    choices = simulate_choices(probs, rng=np.random.default_rng(123))
    share_a = (choices == "a").mean()
    assert share_a == pytest.approx(0.7, abs=0.02)


def test_mnl_simulate_end_to_end():
    choosers = pd.DataFrame({"income_k": [10.0, 200.0], "size": [1, 5]})
    choices = mnl_simulate(choosers, _spec(), rng=np.random.default_rng(1))
    assert list(choices.index) == [0, 1]
    assert set(choices).issubset({"low", "high"})


def test_load_spec_coerces_and_validates():
    spec = load_spec(AUTO_SPEC)
    assert "expression" in spec.columns
    assert {"cars_0", "cars_1", "cars_2", "cars_3p"}.issubset(spec.columns)
    assert spec["cars_1"].dtype.kind == "f"


def test_load_spec_rejects_missing_expression(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,cars_0\n1,0\n")
    with pytest.raises(ValueError, match="expression"):
        load_spec(bad)
