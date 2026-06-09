"""Discrete-choice modeling engine.

Every demand model in an ABM — auto ownership, workplace location, daily activity
pattern, tour and trip mode — is a *discrete choice*: a chooser picks one
alternative from a set, with probabilities from a random-utility (logit) model.
Rather than hand-code each, ActivitySim-style models express the **utility** as a
spec: a table of expressions × per-alternative coefficients. This package
evaluates such specs, forms multinomial-logit probabilities, and simulates
choices with a seeded RNG.
"""

from __future__ import annotations

from .destination import destination_choice
from .logit import (
    evaluate_utilities,
    mnl_probabilities,
    mnl_simulate,
    simulate_choices,
)
from .spec import load_spec

__all__ = [
    "destination_choice",
    "evaluate_utilities",
    "load_spec",
    "mnl_probabilities",
    "mnl_simulate",
    "simulate_choices",
]
