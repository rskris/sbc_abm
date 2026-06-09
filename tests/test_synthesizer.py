"""Tests for the end-to-end population synthesizer."""

from __future__ import annotations

import numpy as np
import pandas as pd

from sbcabm.popsyn.synthesizer import build_incidence, synthesize


def test_synthesize_hits_household_totals(popsyn_inputs):
    result = synthesize(
        seed_households=popsyn_inputs["seed_households"],
        seed_persons=popsyn_inputs["seed_persons"],
        incidence=popsyn_inputs["incidence"],
        controls=popsyn_inputs["controls"],
        total_households_control="total_households",
        seed=42,
    )

    controls = popsyn_inputs["controls"]
    by_zone = result.households.groupby("zone_id").size()
    for zone_id, target in controls["total_households"].items():
        assert by_zone[zone_id] == int(target)

    # Global counts and id uniqueness.
    assert result.n_households == int(controls["total_households"].sum())
    assert result.households["household_id"].is_unique
    assert result.persons["person_id"].is_unique


def test_persons_link_back_to_households(popsyn_inputs):
    result = synthesize(
        seed_households=popsyn_inputs["seed_households"],
        seed_persons=popsyn_inputs["seed_persons"],
        incidence=popsyn_inputs["incidence"],
        controls=popsyn_inputs["controls"],
        total_households_control="total_households",
        seed=1,
    )
    # Every person points at a real household, and zones are consistent.
    hh_ids = set(result.households["household_id"])
    assert set(result.persons["household_id"]).issubset(hh_ids)

    merged = result.persons.merge(
        result.households[["household_id", "zone_id"]],
        on="household_id",
        suffixes=("_p", "_h"),
    )
    assert (merged["zone_id_p"] == merged["zone_id_h"]).all()


def test_synthesized_marginals_are_close(popsyn_inputs):
    # The synthetic population should approximately reproduce person controls.
    result = synthesize(
        seed_households=popsyn_inputs["seed_households"],
        seed_persons=popsyn_inputs["seed_persons"],
        incidence=popsyn_inputs["incidence"],
        controls=popsyn_inputs["controls"],
        total_households_control="total_households",
        seed=42,
    )
    persons = result.persons
    controls = popsyn_inputs["controls"]

    under18 = persons[persons["age"] < 18].groupby("zone_id").size()
    for zone_id, target in controls["pers_under18"].items():
        # Integerization + finite seed → allow a modest tolerance.
        assert abs(int(under18.get(zone_id, 0)) - int(target)) <= 0.15 * target


def test_reproducible_given_seed(popsyn_inputs):
    kwargs = dict(
        seed_households=popsyn_inputs["seed_households"],
        seed_persons=popsyn_inputs["seed_persons"],
        incidence=popsyn_inputs["incidence"],
        controls=popsyn_inputs["controls"],
        total_households_control="total_households",
        seed=99,
    )
    a = synthesize(**kwargs)
    b = synthesize(**kwargs)
    pd.testing.assert_frame_equal(a.households, b.households)
    pd.testing.assert_frame_equal(a.persons, b.persons)


def test_build_incidence_from_categories():
    seed = pd.DataFrame(
        {"hh_size": [1, 2, 3]}, index=pd.Index([10, 11, 12], name="seed_household_id")
    )
    persons = pd.DataFrame(
        {
            "seed_household_id": [10, 11, 11, 12, 12, 12],
            "age": [40, 38, 9, 50, 12, 7],
        }
    )
    children = (
        persons[persons["age"] < 18].groupby("seed_household_id").size()
    )
    incidence = build_incidence(
        seed,
        household_categories={"hh_size_1": seed["hh_size"] == 1},
        person_categories={"pers_under18": children},
    )
    assert list(incidence["hh_size_1"]) == [1.0, 0.0, 0.0]
    # hh 10 has 0 children, hh 11 has 1, hh 12 has 2.
    assert list(incidence["pers_under18"]) == [0.0, 1.0, 2.0]


def test_diagnostics_report_convergence(popsyn_inputs):
    result = synthesize(
        seed_households=popsyn_inputs["seed_households"],
        seed_persons=popsyn_inputs["seed_persons"],
        incidence=popsyn_inputs["incidence"],
        controls=popsyn_inputs["controls"],
        total_households_control="total_households",
    )
    diag = result.diagnostics
    assert set(diag["zone_id"]) == set(popsyn_inputs["controls"].index)
    assert diag["balance_converged"].all()
    assert (diag["max_control_gap"] < 1e-3).all()
    assert np.all(diag["synthesized_households"].to_numpy() > 0)
