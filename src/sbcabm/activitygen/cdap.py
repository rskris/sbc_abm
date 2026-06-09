"""Coordinated Daily Activity Pattern (CDAP).

Assigns each person one of three top-level day patterns:

* ``mandatory`` — has at least one mandatory activity (work or school),
* ``nonmandatory`` — no mandatory activity but travels for other purposes,
* ``home`` — stays home all day.

Two routines are provided:

* :func:`run_cdap` — a person-level multinomial logit (independent persons).
* :func:`run_cdap_household` — ActivitySim-style **household interaction**: a
  household's members choose their patterns *jointly*, so the utility of a
  combination adds an interaction term for each pair of members, letting families
  coordinate (e.g. stay home together). The joint pattern is sampled from the
  softmax over all member-pattern combinations.

Person utilities come from ``configs/specs/cdap.csv``; pairwise interaction
coefficients default to :data:`DEFAULT_INTERACTION`.
"""

from __future__ import annotations

import itertools
import logging

import numpy as np
import pandas as pd

from ..choice import evaluate_utilities, mnl_simulate

logger = logging.getLogger("sbcabm.activitygen.cdap")

CDAP_PATTERNS = ("mandatory", "nonmandatory", "home")

# Pairwise interaction utility added when two household members take the given
# pair of patterns (symmetric; missing pairs are 0). Positive values encourage
# coordination — families tend to be home together or share non-mandatory days.
DEFAULT_INTERACTION: dict[frozenset[str], float] = {
    frozenset({"home"}): 0.5,  # both home
    frozenset({"nonmandatory"}): 0.3,  # both non-mandatory
    frozenset({"mandatory", "home"}): -0.2,  # one out, one home: mild discord
    frozenset({"nonmandatory", "home"}): 0.1,
}
_MAX_MODELED = 5  # cap joint enumeration (3^k); extra members modeled independently


def _prepare(persons: pd.DataFrame) -> pd.DataFrame:
    choosers = persons.copy()
    if "AGEP" not in choosers.columns:
        raise KeyError("persons must carry 'AGEP' for CDAP")
    choosers["AGEP"] = pd.to_numeric(choosers["AGEP"], errors="coerce").fillna(0)
    if "workplace_zone" in choosers.columns:
        choosers["has_workplace"] = choosers["workplace_zone"].notna()
    else:
        choosers["has_workplace"] = False
    return choosers


def run_cdap(persons: pd.DataFrame, spec: pd.DataFrame, *, rng: np.random.Generator) -> pd.Series:
    """Person-level CDAP (independent persons). Returns a Series of patterns."""
    choices = mnl_simulate(_prepare(persons), spec, rng=rng)
    logger.info("CDAP (person) patterns: %s", choices.value_counts().to_dict())
    return choices


def run_cdap_household(
    persons: pd.DataFrame,
    spec: pd.DataFrame,
    *,
    rng: np.random.Generator,
    interaction: dict[frozenset[str], float] | None = None,
    household_col: str = "household_id",
) -> pd.Series:
    """Household-interaction CDAP: members choose their patterns jointly."""
    interaction = DEFAULT_INTERACTION if interaction is None else interaction
    choosers = _prepare(persons)
    utilities = evaluate_utilities(choosers, spec)
    patterns = list(utilities.columns)

    result = pd.Series(index=persons.index, dtype=object)
    for _, group in choosers.groupby(household_col, sort=False):
        member_idx = list(group.index)
        modeled, extra = member_idx[:_MAX_MODELED], member_idx[_MAX_MODELED:]
        _assign_joint(result, modeled, utilities, patterns, interaction, rng)
        for member in extra:  # overflow members: independent choice
            probs = _softmax(utilities.loc[member].to_numpy(dtype=float))
            result.loc[member] = patterns[rng.choice(len(patterns), p=probs)]

    logger.info("CDAP (household) patterns: %s", result.value_counts().to_dict())
    return result


def _assign_joint(result, modeled, utilities, patterns, interaction, rng) -> None:
    base = utilities.loc[modeled].to_numpy(dtype=float)  # (m, P)
    combos = list(itertools.product(range(len(patterns)), repeat=len(modeled)))
    joint_utility = np.empty(len(combos))
    for c, combo in enumerate(combos):
        u = sum(base[k, combo[k]] for k in range(len(modeled)))
        for a in range(len(modeled)):
            for b in range(a + 1, len(modeled)):
                u += interaction.get(frozenset({patterns[combo[a]], patterns[combo[b]]}), 0.0)
        joint_utility[c] = u

    probs = _softmax(joint_utility)
    chosen = combos[rng.choice(len(combos), p=probs)]
    for k, member in enumerate(modeled):
        result.loc[member] = patterns[chosen[k]]


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - values.max()
    exp = np.exp(shifted)
    return exp / exp.sum()
