# Epic 3 — Discrete-choice engine & long-term choices

**Status: Done** · Delivers FR6–FR7.
Goal: the reusable choice machinery, and the once-per-person decisions that
condition all daily travel.

## Stories

### 3.1 Choice engine (MNL) — Done
CSV utility specs (`expression` × per-alternative coefficients; `@python` or
column refs, safe-builtins namespace); stable MNL with availability; seeded
simulation matching probabilities in expectation.
*Evidence:* `src/sbcabm/choice/{spec,logit}.py`; `tests/test_choice.py`.

### 3.2 Destination-choice engine — Done
Shared β_time·time + β_size·ln(size) logit over zones; per-origin probability
sharing; optional uniform per-chooser alternative sampling (correction cancels).
*Evidence:* `src/sbcabm/choice/destination.py`; `tests/test_longterm_extra.py`.

### 3.3 Auto ownership — Done
MNL over 0/1/2/3+ vehicles (size, income, densities), spec
`configs/specs/auto_ownership.csv`; income gradient asserted.
*Evidence:* `src/sbcabm/longterm/auto_ownership.py`; `tests/test_longterm.py`.

### 3.4 Work & school location — Done
Workplace (employment size term) and school (education employment, total
fallback) via the destination engine, written onto eligible persons.
*Evidence:* `src/sbcabm/longterm/{work_location,school_location}.py`.

### 3.5 Transit pass & telecommute — Done
Binary pass model (carless gradient asserted) and 3-level telecommute model
(income gradient asserted); specs in `configs/specs/`.
*Evidence:* `src/sbcabm/longterm/mobility.py`; `tests/test_longterm_extra.py`.

### 3.6 Nested logit — Done *(delivered under Epic 5, recorded here as engine)*
Logsum nests with λ∈(0,1], availability, λ=1 ≡ MNL, red-bus/blue-bus damping.
*Evidence:* `src/sbcabm/choice/nested_logit.py`; `tests/test_nested_logit.py`.
