"""Tests for list balancing / IPU weight solving."""

from __future__ import annotations

import numpy as np
import pytest

from sbcabm.popsyn.balancer import balance_weights


def test_single_total_control_spreads_evenly():
    # Four identical households, one control: total = 100 → 25 each.
    incidence = np.ones((4, 1))
    result = balance_weights(incidence, np.array([100.0]))
    assert result.converged
    np.testing.assert_allclose(result.weights, 25.0, atol=1e-6)


def test_matches_multiple_binary_controls():
    # Two attributes; weights must satisfy both marginal sets at once.
    #   household: [size1?, size2plus?, low?, high?]
    incidence = np.array(
        [
            [1, 0, 1, 0],  # size1, low
            [1, 0, 0, 1],  # size1, high
            [0, 1, 1, 0],  # size2+, low
            [0, 1, 0, 1],  # size2+, high
        ],
        dtype=float,
    )
    controls = np.array([30.0, 70.0, 40.0, 60.0])  # size1, size2+, low, high
    result = balance_weights(incidence, controls, tolerance=1e-9)

    assert result.converged
    np.testing.assert_allclose(result.weighted_totals(incidence), controls, rtol=1e-6)


def test_real_valued_person_incidence():
    # A person-level control (persons under 18) where households contribute >1.
    incidence = np.array(
        [
            [1, 0],  # 1 hh, 0 children
            [1, 2],  # 1 hh, 2 children
        ],
        dtype=float,
    )
    controls = np.array([10.0, 8.0])  # 10 households, 8 children
    result = balance_weights(incidence, controls, tolerance=1e-10)
    assert result.converged
    totals = result.weighted_totals(incidence)
    np.testing.assert_allclose(totals, controls, rtol=1e-5)


def test_respects_initial_weights_direction():
    incidence = np.ones((3, 1))
    init = np.array([1.0, 2.0, 3.0])
    result = balance_weights(incidence, np.array([60.0]), initial_weights=init)
    # Total honoured, and the seed's relative ordering preserved.
    assert result.weights.sum() == pytest.approx(60.0, rel=1e-6)
    assert result.weights[0] < result.weights[1] < result.weights[2]


def test_infeasible_control_raises():
    incidence = np.array([[1.0, 0.0], [1.0, 0.0]])  # nothing contributes to control 1
    with pytest.raises(ValueError, match="no seed household contributes"):
        balance_weights(incidence, np.array([10.0, 5.0]))


def test_shape_validation():
    with pytest.raises(ValueError, match="controls has shape"):
        balance_weights(np.ones((3, 2)), np.array([1.0]))
