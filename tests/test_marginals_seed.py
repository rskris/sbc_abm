"""Tests for ACS marginal assembly and PUMS seed recoding."""

from __future__ import annotations

import pandas as pd
import pytest

from sbcabm.popsyn.marginals import build_controls
from sbcabm.popsyn.seed import apply_recodes, build_seed_incidence
from sbcabm.popsyn.specs import Bin, ControlSpec, Recode


def test_build_controls_sums_acs_variables():
    acs = pd.DataFrame(
        {
            "GEOID": ["a", "b"],
            "T_001E": [100, 50],
            "X_002E": [30, 20],
            "X_003E": [10, 5],
        }
    )
    specs = (
        ControlSpec("total_households", "household", ("T_001E",), None),
        ControlSpec("x_combined", "household", ("X_002E", "X_003E"), "x", "yes"),
    )
    controls = build_controls(acs, specs)
    assert controls.index.name == "zone_id"
    assert list(controls.loc["a"]) == [100, 40]
    assert list(controls.loc["b"]) == [50, 25]


def test_build_controls_missing_variable_is_zero_with_warning(caplog):
    acs = pd.DataFrame({"GEOID": ["a"], "T_001E": [10]})
    specs = (
        ControlSpec("total_households", "household", ("T_001E",), None),
        ControlSpec("ghost", "household", ("NOPE_001E",), "x", "y"),
    )
    controls = build_controls(acs, specs)
    assert controls.loc["a", "ghost"] == 0.0
    assert "missing ACS variables" in caplog.text


def test_build_controls_requires_total_variables():
    acs = pd.DataFrame({"GEOID": ["a"], "OTHER_001E": [10]})
    specs = (ControlSpec("total_households", "household", ("T_001E",), None),)
    with pytest.raises(KeyError, match="total_households"):
        build_controls(acs, specs)


def test_apply_recodes_bins_numeric_to_labels():
    df = pd.DataFrame({"NP": [1, 2, 4, 7]})
    recode = Recode(
        "hh_size",
        "NP",
        (Bin(1, 1, "one"), Bin(2, 3, "small"), Bin(4, 99, "large")),
    )
    out = apply_recodes(df, (recode,))
    assert list(out["hh_size"]) == ["one", "small", "large", "large"]


def test_apply_recodes_unmatched_is_nan():
    df = pd.DataFrame({"AGEP": [-1, 5]})
    recode = Recode("age_group", "AGEP", (Bin(0, 17, "child"),))
    out = apply_recodes(df, (recode,))
    assert pd.isna(out["age_group"].iloc[0])
    assert out["age_group"].iloc[1] == "child"


def test_build_seed_incidence_household_and_person():
    seed_hh = pd.DataFrame(
        {"hh_size": ["size_1", "size_2", "size_2"]},
        index=pd.Index([10, 11, 12], name="seed_household_id"),
    )
    seed_persons = pd.DataFrame(
        {
            "seed_household_id": [10, 11, 11, 12, 12, 12],
            "age_group": ["adult", "adult", "child", "adult", "child", "child"],
        }
    )
    specs = (
        ControlSpec("total_households", "household", (), None),
        ControlSpec("size_1", "household", (), "hh_size", "size_1"),
        ControlSpec("size_2", "household", (), "hh_size", "size_2"),
        ControlSpec("kids", "person", (), "age_group", "child"),
    )
    incidence = build_seed_incidence(seed_hh, seed_persons, specs)
    assert list(incidence["total_households"]) == [1.0, 1.0, 1.0]
    assert list(incidence["size_1"]) == [1.0, 0.0, 0.0]
    assert list(incidence["size_2"]) == [0.0, 1.0, 1.0]
    # hh 10 → 0 kids, hh 11 → 1, hh 12 → 2.
    assert list(incidence["kids"]) == [0.0, 1.0, 2.0]


def test_build_seed_incidence_rejects_unknown_level():
    seed_hh = pd.DataFrame({"x": [1]}, index=pd.Index([1], name="seed_household_id"))
    specs = (ControlSpec("bad", "vehicle", (), "x", 1),)
    with pytest.raises(ValueError, match="unknown level"):
        build_seed_incidence(seed_hh, pd.DataFrame(columns=["seed_household_id"]), specs)


def test_specs_default_scheme_is_consistent():
    from sbcabm.popsyn.specs import all_control_specs, default_recodes

    specs = all_control_specs()
    names = [s.name for s in specs]
    assert "total_households" in names
    assert len(names) == len(set(names))  # unique control names

    # Every household control (except the total) references a recode target,
    # and every person control references the age recode.
    recode_targets = {r.target for r in default_recodes()}
    for spec in specs:
        if spec.seed_attribute is not None:
            assert spec.seed_attribute in recode_targets
    # Every value a control selects is producible by its recode.
    recode_labels = {b.label for r in default_recodes() for b in r.bins}
    for spec in specs:
        if spec.seed_value is not None:
            assert spec.seed_value in recode_labels


def test_acs_variable_id_formatting():
    from sbcabm.popsyn.specs import acs_variables, all_control_specs

    variables = acs_variables(all_control_specs())
    assert all(v.endswith("E") for v in variables)
    assert "B11016_001E" in variables  # total households anchor
