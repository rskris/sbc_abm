# BMAD-Method in this repository

This project is run with the **BMAD-Method** (Breakthrough Method for Agile
AI-Driven Development): planning produces a small set of authoritative
documents, and all development proceeds **story-by-story** against them.

## Artifacts

| Artifact | BMAD role | File |
|---|---|---|
| Project brief | Analyst | [`project-brief.md`](project-brief.md) |
| Product requirements (PRD) | PM | [`prd.md`](prd.md) |
| Architecture | Architect | [`architecture.md`](architecture.md) (extends [`../ARCHITECTURE.md`](../ARCHITECTURE.md)) |
| Epics | PM / SM | [`epics/`](epics/) — one file per epic, stories inside |
| Dev-ready stories | Scrum Master | [`stories/`](stories/) — sharded stories queued for a dev agent |

## Workflow

1. **Plan** — brief → PRD → architecture. Done once, amended via change requests.
2. **Shard** — the PM/SM breaks the PRD into epics, and epics into stories with
   acceptance criteria. A story is *Ready* when a dev agent could implement it
   with no other context than the story file + architecture doc.
3. **Develop** — the dev agent implements exactly one story at a time:
   implement → test (all acceptance criteria become tests) → lint → commit,
   marking the story *Done* in its epic file.
4. **QA gate** — CI (ruff + pytest on 3.10–3.12) must pass; behavioral
   acceptance criteria must be asserted in `tests/`.

## Status convention

Stories carry one of: `Draft` → `Approved` → `InProgress` → `Done`.
Epics 1–5 were delivered before BMAD adoption and are retro-documented with
their stories marked `Done`, each citing the modules and tests that satisfy it.

## Ground rules (binding on dev agents)

- Never implement beyond the current story's scope; raise a change request
  instead of silently expanding.
- Every acceptance criterion maps to at least one test in `tests/`.
- Model coefficients/specs are **data** (`configs/specs/*.csv`), never code.
- All stochastic behavior flows from the run's single `random_seed`.
- `ruff check src tests` must exit 0; check the exit code, not the output.
