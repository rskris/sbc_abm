"""Tests for largest-remainder integerization of weights."""

from __future__ import annotations

import numpy as np

from sbcabm.popsyn.integerize import integerize_weights


def test_sum_equals_explicit_target():
    weights = np.array([1.4, 2.6, 0.9, 5.1])
    counts = integerize_weights(weights, target_total=10)
    assert counts.sum() == 10
    assert counts.dtype.kind == "i"
    assert (counts >= 0).all()


def test_default_target_is_rounded_sum():
    weights = np.array([1.4, 2.6, 0.9, 5.1])  # sums to 10.0
    counts = integerize_weights(weights)
    assert counts.sum() == 10


def test_largest_remainder_allocation():
    # All equal halves; target 2 → exactly two ones, picked by remainder.
    weights = np.array([0.5, 0.5, 0.5, 0.5])
    counts = integerize_weights(weights, target_total=2, rng=np.random.default_rng(0))
    assert counts.sum() == 2
    assert set(np.unique(counts)).issubset({0, 1})


def test_floor_preserved_for_large_integer_parts():
    weights = np.array([10.2, 0.3, 0.3, 0.2])  # floors: 10,0,0,0 sum 10; target 11
    counts = integerize_weights(weights, target_total=11)
    assert counts[0] >= 10  # the big one keeps (at least) its floor
    assert counts.sum() == 11


def test_target_below_floor_sum_removes_units():
    weights = np.array([3.9, 3.9, 3.9])  # floors sum to 9; ask for 8
    counts = integerize_weights(weights, target_total=8)
    assert counts.sum() == 8
    assert (counts >= 0).all()


def test_target_far_above_floor_sum():
    # Sparse weights (all < 1, floors all 0) but a large target → even base
    # share plus largest-remainder leftover, summing exactly to target.
    weights = np.array([0.5, 0.5, 0.5, 0.5])
    counts = integerize_weights(weights, target_total=10)
    assert counts.sum() == 10
    assert (counts >= 0).all()
    assert counts.max() - counts.min() <= 1  # spread evenly


def test_target_far_below_floor_sum():
    # Floors sum to 30; ask for 7 → must remove 23 units without going negative.
    weights = np.array([10.1, 10.2, 10.3])
    counts = integerize_weights(weights, target_total=7)
    assert counts.sum() == 7
    assert (counts >= 0).all()


def test_empty_weights():
    assert integerize_weights(np.array([]), target_total=0).tolist() == []


def test_reproducible_with_seed():
    weights = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
    a = integerize_weights(weights, target_total=3, rng=np.random.default_rng(7))
    b = integerize_weights(weights, target_total=3, rng=np.random.default_rng(7))
    np.testing.assert_array_equal(a, b)
