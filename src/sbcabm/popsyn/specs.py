"""Control & recode specifications that bind Census data to synthesis.

Population synthesis needs two things expressed in the *same* category system:

* **marginal controls** per zone — assembled by summing ACS detailed-table
  estimate columns (e.g. household size, income, persons by age), and
* **seed incidence** — how each PUMS seed household contributes to each control,
  derived by recoding PUMS micro-data variables (NP, HINCP, AGEP, …) into those
  same categories.

A :class:`ControlSpec` names a control once and carries both halves: the ACS
variables that form its marginal and the recoded seed attribute/value that forms
its incidence. This keeps the two sides definitionally consistent and lets the
whole scheme be tuned as data, not code.

The default Santa Barbara County scheme below is a **documented draft**: the ACS
variable IDs follow the standard table structures (B11016 household size, B19001
income, B01001 sex-by-age) but should be validated against the live API for the
configured vintage before production use.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ControlSpec:
    """One marginal control and how seed households contribute to it."""

    name: str
    level: str  # "household" or "person"
    acs_variables: tuple[str, ...]  # estimate columns summed to form the marginal
    seed_attribute: str | None  # recoded seed column (None ⇒ every unit matches)
    seed_value: object | None = None  # category value this control selects


@dataclass(frozen=True)
class Bin:
    """An inclusive numeric range mapped to a categorical label."""

    low: float
    high: float
    label: str


@dataclass(frozen=True)
class Recode:
    """Map a numeric PUMS column into a categorical column via bins."""

    target: str
    source: str
    bins: tuple[Bin, ...]


def _acs(table: str, numbers: list[int]) -> tuple[str, ...]:
    """Render ACS estimate variable IDs, e.g. _acs('B01001', [3,4]) → B01001_003E."""
    return tuple(f"{table}_{n:03d}E" for n in numbers)


# --- Default Santa Barbara County scheme (draft; verify against live API) -----

HOUSEHOLD_CONTROLS: tuple[ControlSpec, ...] = (
    # Total households — every seed household contributes 1; integerization target.
    ControlSpec("total_households", "household", _acs("B11016", [1]), None),
    # Household size (B11016 Household Type by Size; family hh are 2+ by design).
    ControlSpec("size_1", "household", _acs("B11016", [10]), "hh_size", "size_1"),
    ControlSpec("size_2", "household", _acs("B11016", [3, 11]), "hh_size", "size_2"),
    ControlSpec("size_3", "household", _acs("B11016", [4, 12]), "hh_size", "size_3"),
    ControlSpec(
        "size_4plus",
        "household",
        _acs("B11016", [5, 6, 7, 8, 13, 14, 15, 16]),
        "hh_size",
        "size_4plus",
    ),
    # Household income (B19001, 16 brackets) grouped into four bands.
    ControlSpec(
        "inc_lt35k", "household", _acs("B19001", [2, 3, 4, 5, 6, 7]), "hh_income", "inc_lt35k"
    ),
    ControlSpec(
        "inc_35_75", "household", _acs("B19001", [8, 9, 10, 11, 12]), "hh_income", "inc_35_75"
    ),
    ControlSpec(
        "inc_75_150", "household", _acs("B19001", [13, 14, 15]), "hh_income", "inc_75_150"
    ),
    ControlSpec(
        "inc_150plus", "household", _acs("B19001", [16, 17]), "hh_income", "inc_150plus"
    ),
)

# Persons by age (B01001 Sex by Age): under-18 vs adult, both sexes.
_MALE_UNDER18 = [3, 4, 5, 6]
_FEMALE_UNDER18 = [27, 28, 29, 30]
_MALE_ADULT = list(range(7, 26))  # 18-19 … 85+
_FEMALE_ADULT = list(range(31, 50))

PERSON_CONTROLS: tuple[ControlSpec, ...] = (
    ControlSpec(
        "pers_under18",
        "person",
        _acs("B01001", _MALE_UNDER18 + _FEMALE_UNDER18),
        "age_group",
        "under18",
    ),
    ControlSpec(
        "pers_adult",
        "person",
        _acs("B01001", _MALE_ADULT + _FEMALE_ADULT),
        "age_group",
        "adult18plus",
    ),
)

# PUMS recodes producing the seed attributes the controls reference.
PUMS_RECODES: tuple[Recode, ...] = (
    Recode(
        "hh_size",
        "NP",
        (
            Bin(1, 1, "size_1"),
            Bin(2, 2, "size_2"),
            Bin(3, 3, "size_3"),
            Bin(4, 10_000, "size_4plus"),
        ),
    ),
    Recode(
        "hh_income",
        "HINCP",
        (
            Bin(-1e12, 34_999, "inc_lt35k"),
            Bin(35_000, 74_999, "inc_35_75"),
            Bin(75_000, 149_999, "inc_75_150"),
            Bin(150_000, 1e12, "inc_150plus"),
        ),
    ),
    Recode(
        "age_group",
        "AGEP",
        (Bin(0, 17, "under18"), Bin(18, 200, "adult18plus")),
    ),
)


def all_control_specs() -> tuple[ControlSpec, ...]:
    return HOUSEHOLD_CONTROLS + PERSON_CONTROLS


def default_recodes() -> tuple[Recode, ...]:
    return PUMS_RECODES


def acs_variables(specs: tuple[ControlSpec, ...]) -> list[str]:
    """Unique ACS estimate columns needed by the given specs (sorted)."""
    seen: set[str] = set()
    for spec in specs:
        seen.update(spec.acs_variables)
    return sorted(seen)


# PUMS columns needed by ingestion. SERIALNO links persons to households.
PUMS_HOUSEHOLD_VARIABLES: tuple[str, ...] = ("SERIALNO", "NP", "HINCP", "WGTP")
PUMS_PERSON_VARIABLES: tuple[str, ...] = ("SERIALNO", "SPORDER", "AGEP", "PWGTP")
