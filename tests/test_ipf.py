"""Tests for N-dimensional Iterative Proportional Fitting."""

from __future__ import annotations

import numpy as np
import pytest

from sbcabm.popsyn.ipf import ipf


def test_uniform_seed_matches_known_solution():
    # Classic 2x2: a uniform seed fit to row marginals [10, 20] and
    # column marginals [15, 15] has the closed-form solution [[5,5],[10,10]].
    seed = np.ones((2, 2))
    result = ipf(seed, [np.array([10.0, 20.0]), np.array([15.0, 15.0])])

    assert result.converged
    np.testing.assert_allclose(result.fitted, [[5, 5], [10, 10]], atol=1e-6)
    np.testing.assert_allclose(result.fitted.sum(axis=1), [10, 20], atol=1e-6)
    np.testing.assert_allclose(result.fitted.sum(axis=0), [15, 15], atol=1e-6)


def test_preserves_seed_association():
    # A skewed seed should keep its odds ratio while hitting the marginals.
    seed = np.array([[2.0, 1.0], [1.0, 2.0]])
    result = ipf(seed, [np.array([10.0, 10.0]), np.array([10.0, 10.0])])
    assert result.converged
    np.testing.assert_allclose(result.fitted.sum(axis=1), [10, 10], atol=1e-6)
    np.testing.assert_allclose(result.fitted.sum(axis=0), [10, 10], atol=1e-6)
    # Odds ratio (a*d)/(b*c) is invariant under IPF scaling.
    f = result.fitted
    assert (f[0, 0] * f[1, 1]) / (f[0, 1] * f[1, 0]) == pytest.approx(4.0, rel=1e-6)


def test_structural_zeros_stay_zero():
    seed = np.array([[1.0, 0.0], [1.0, 1.0]])
    result = ipf(seed, [np.array([5.0, 10.0]), np.array([9.0, 6.0])])
    assert result.fitted[0, 1] == 0.0


def test_three_dimensional():
    seed = np.ones((2, 3, 2))
    marginals = [
        np.array([30.0, 30.0]),
        np.array([20.0, 20.0, 20.0]),
        np.array([24.0, 36.0]),
    ]
    result = ipf(seed, marginals)
    assert result.converged
    for axis, target in enumerate(marginals):
        summed = result.fitted.sum(axis=tuple(a for a in range(3) if a != axis))
        np.testing.assert_allclose(summed, target, atol=1e-6)


def test_rejects_mismatched_totals():
    with pytest.raises(ValueError, match="totals disagree"):
        ipf(np.ones((2, 2)), [np.array([10.0, 10.0]), np.array([5.0, 5.0])])


def test_rejects_wrong_number_of_marginals():
    with pytest.raises(ValueError, match="marginals"):
        ipf(np.ones((2, 2)), [np.array([10.0, 10.0])])
