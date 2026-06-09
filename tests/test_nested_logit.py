"""Tests for the nested-logit engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sbcabm.choice import Nest, mnl_probabilities, nested_logit_probabilities


def _utils(rows):
    return pd.DataFrame(rows, columns=["da", "wt", "wk", "bk"])


_NESTS = [
    Nest("auto", 0.6, ("da",)),
    Nest("transit", 0.6, ("wt",)),
    Nest("active", 0.6, ("wk", "bk")),
]


def test_probabilities_sum_to_one():
    utils = _utils([[0.0, -0.5, -1.0, -1.5], [1.0, 1.0, 0.0, 0.0]])
    probs = nested_logit_probabilities(utils, _NESTS)
    np.testing.assert_allclose(probs.sum(axis=1), 1.0)


def test_lambda_one_reduces_to_mnl():
    utils = _utils([[0.0, -0.5, -1.0, -1.5], [0.3, 0.1, -0.2, 0.4]])
    nests = [Nest("a", 1.0, ("da",)), Nest("b", 1.0, ("wt",)), Nest("c", 1.0, ("wk", "bk"))]
    nl = nested_logit_probabilities(utils, nests)
    mnl = mnl_probabilities(utils)
    pd.testing.assert_frame_equal(nl, mnl, atol=1e-9)


def test_availability_zeros_unavailable():
    utils = _utils([[0.0, 0.0, 0.0, 0.0]])
    avail = pd.DataFrame([[True, False, True, True]], columns=["da", "wt", "wk", "bk"])
    probs = nested_logit_probabilities(utils, _NESTS, availability=avail)
    assert probs.iloc[0]["wt"] == pytest.approx(0.0)
    assert probs.sum(axis=1).iloc[0] == pytest.approx(1.0)


def test_nesting_dampens_red_bus_blue_bus():
    # Two near-identical "active" alternatives. Under MNL they split the market
    # and steal share from the lone auto alt (IIA). Nesting them together keeps
    # more share on auto. Make wt unavailable to isolate auto vs active.
    utils = _utils([[0.0, -np.inf, 0.0, 0.0]])  # da, wt(unavail), wk, bk all equal
    mnl = mnl_probabilities(utils)
    nested = [
        Nest("auto", 0.5, ("da",)),
        Nest("transit", 0.5, ("wt",)),
        Nest("active", 0.5, ("wk", "bk")),
    ]
    nl = nested_logit_probabilities(utils, nested)
    # MNL: da = 1/3. Nested: the correlated wk/bk pair behaves more like one
    # alternative, so da gets closer to 1/2.
    assert mnl.iloc[0]["da"] == pytest.approx(1 / 3, abs=1e-6)
    assert nl.iloc[0]["da"] > mnl.iloc[0]["da"]
    assert nl.iloc[0]["da"] < 0.5


def test_rejects_bad_partition():
    utils = _utils([[0.0, 0.0, 0.0, 0.0]])
    with pytest.raises(ValueError, match="partition"):
        nested_logit_probabilities(utils, [Nest("a", 0.7, ("da", "wt"))])


def test_rejects_bad_coefficient():
    with pytest.raises(ValueError, match="λ must be"):
        Nest("bad", 1.5, ("da",))


def test_all_unavailable_row_is_nan():
    utils = _utils([[0.0, 0.0, 0.0, 0.0]])
    avail = pd.DataFrame([[False, False, False, False]], columns=["da", "wt", "wk", "bk"])
    probs = nested_logit_probabilities(utils, _NESTS, availability=avail)
    assert probs.iloc[0].isna().all()
