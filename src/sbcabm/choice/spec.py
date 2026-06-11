"""Utility specification files.

A spec is a CSV with an ``expression`` column and one column per alternative
giving that expression's coefficient in the alternative's utility. An optional
``label``/``description`` column documents the row and is ignored by the math.

Expressions are evaluated against the choosers table (see ``logit.py``):

* ``@<python>`` — a Python expression over chooser columns, e.g. ``@HINCP/1000``
  or ``@(NP > 3)``; ``1`` (or ``@1``) is the constant term (ASC).
* ``<column>`` — a bare chooser column name.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

EXPRESSION_COLUMN = "expression"
_META_COLUMNS = {EXPRESSION_COLUMN, "label", "description"}


def load_spec(path: str | Path, *, expr_col: str = EXPRESSION_COLUMN) -> pd.DataFrame:
    """Load and validate a utility spec CSV.

    Returns the spec with its ``expression`` column intact and every
    alternative column coerced to float (blank coefficients become ``NaN`` and
    are skipped during evaluation).
    """
    spec = pd.read_csv(path)
    if expr_col not in spec.columns:
        raise ValueError(f"spec at {path} is missing the '{expr_col}' column")

    alt_columns = [c for c in spec.columns if c not in _META_COLUMNS]
    if not alt_columns:
        raise ValueError(f"spec at {path} has no alternative columns")

    spec[expr_col] = spec[expr_col].astype(str)
    for col in alt_columns:
        spec[col] = pd.to_numeric(spec[col], errors="coerce")
    return spec


def alternatives(spec: pd.DataFrame, *, expr_col: str = EXPRESSION_COLUMN) -> list[str]:
    """The alternative (utility) columns of a spec, in order."""
    return [c for c in spec.columns if c not in _META_COLUMNS]
