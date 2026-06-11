# Epic 0 — Foundation

**Status: Done** · Delivers FR12, NFR1–NFR5.
Goal: a packaged, configurable, CI-guarded skeleton any later story can build on.

## Stories

### 0.1 Project scaffolding — Done
Packaging (`pyproject.toml`, src layout, extras), MIT license, `.gitignore`,
GitHub Actions CI (ruff + pytest, Python 3.10–3.12), web SessionStart hook.
*Evidence:* `pyproject.toml`, `.github/workflows/ci.yml`.

### 0.2 Typed run configuration — Done
One YAML file describes a run: region (SB County FIPS 06083), seed, paths,
data vintages, stages. Frozen dataclasses; env-var API key override; config-dir
recorded so spec paths resolve anywhere.
*Evidence:* `src/sbcabm/config.py`; `tests/test_config_and_pipeline.py`.

### 0.3 Stage pipeline & data store — Done
`DataStore` of named tables; `StageRegistry`; orchestrator runs configured
stages, skipping unimplemented ones with a warning (config documents intent).
*Evidence:* `src/sbcabm/pipeline.py`; `tests/test_config_and_pipeline.py`.

### 0.4 CLI — Done
`sbcabm info` (resolved config + stage status) and `sbcabm run --stages ...
[--write]`.
*Evidence:* `src/sbcabm/cli.py`.
