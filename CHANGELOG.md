# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- Documentation consistency pass across `README.md`, `中文說明.md`, `CONTRIBUTING.md`, `SECURITY.md`, and `PUBLIC_SCOPE.md`.
- Clarified version semantics: API release baseline (`0.1.x`) vs runtime data scope (`v0.3.1`) vs visualization style labels (`V1~V6`).
- Clarified public publishing checklist and required pre-publish validations.
- Added `CODE_OF_CONDUCT.md` and linked it from project docs.
- Migrated runtime path naming from the legacy nested backend location to `backend` and updated active config/docs accordingly.
- Added `backend/scripts/start_local.py` with interpreter auto-fallback to reduce startup failure under broken virtualenv setups.
- Added `HEAD` support for read endpoints to improve browser/proxy compatibility (including Safari preflight-style requests).
- Removed optional-chaining syntax from frontend runtime code to avoid parse failures on older Safari engines.
- Refreshed UI theme to daylight-first colors and enabled automatic light/dark follow-system behavior via `prefers-color-scheme`.
- Promoted active runtime scope/version naming to `v0.3.1` across API responses and docs.
- Updated citation hover/pin behavior to prefer original source poem text over explanation snippets.
- Added project-root `.env` auto-loading for runtime defaults when shell variables are not pre-exported.
- Added ASCII Chinese guide entry file `README.zh-TW.md` and pointed root README to it for cross-platform filename visibility.
- Enhanced ingest summaries with source-text coverage (`sources_with_text`/`sources_without_text`) and persisted `source_folder` in run config metadata.
- Added HTML-entity decoding fallback for citation `source_id` path resolution (for filenames like `&#x3c;...&#x3e;`).
- Added corpus-size and source coverage metrics (`corpus_markdown_files`, `source_coverage_percent`) to ingest summary output.
- Updated pipeline run docs to stop recommending low-coverage full parameters (`iterations=6`, `sample_size=30`) for large corpora.
- Added low-coverage warnings in `backend/scripts/trigger_api_run.py` when full-run draw count is likely too small for corpus size.
- Added fail-fast dependency check in `backend/scripts/trigger_api_run.py` for missing `vertexai`, with actionable install hint.
- Added `google-cloud-aiplatform` to `backend/requirements.txt` so generation scripts can import `vertexai` in a clean environment.
- Added startup-time warning in `backend/scripts/start_local.py` when `vertexai` is missing (UI can open, generation endpoints cannot run).
- Extended `GET /runs` response with per-run stats (`nodes`, `citations`, `sources`, text coverage, corpus size, coverage percent).
- Updated runtime UI citation preview to be fixed-position beside the hovered citation card (no mouse-follow jitter).
- Improved node layout spacing to avoid lane overlap in dense stages and normalized card height for consistent readability.
- Added UI controls to toggle edge rendering (`show/hide` and `include weak/far`) and added collapsible left Notes panel.
- Enforced independent scrolling between graph canvas and side panels in desktop layout (reduced scroll coupling).
- Moved right-panel `Citations` section to directly below node meta for player-facing reading priority.
- Added `IMPROVEMENT_ROADMAP.md` to track audited frontend art and backend structure follow-up goals.
- Added run coverage audit API (`GET /runs/{run_id}/audit`) to separate corpus scan, mounting coverage, and citation coverage metrics.
- Added `backend/scripts/audit_run.py` for local JSON audit export and quick coverage summary.
- Added `backend/scripts/sample_fill_quality.py` to sample fill assignments and gate fill-to-citation promotion by quote-in-source validation.
- Added `HANDOFF.md` with role-based architecture notes, verified metrics snapshot, and dual-window execution checklist.
- Persisted `ingest_stats` into `runs.config_json` during import, including mounting coverage metrics from `poem_mounting_seed/full.json`.
- Extended `GET /runs` stats to surface mounting coverage fields when available (`mounting_full_*`, `mounting_seed_*`).
- Added long-term roadmap track for sentence/paragraph-level multi-agent consensus review and fine-tuning-oriented evidence governance (Priority D).
- Added explicit context-anchoring requirement in roadmap: sentence/paragraph evidence must remain linked to full-poem context.
- Sanitized legacy `next_window_stack` path segments in audit runtime artifact payloads.

### Security
- Security reporting guidance now explicitly prioritizes GitHub private vulnerability reporting.

## [0.1.0] - 2026-02-22

### Added
- Public migration baseline files: `.gitignore`, `.env.example`, `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`.
- Community templates: issue templates for bug reports and feature requests.
- Public docs refresh for repository root and backend runtime.

### Changed
- Removed personal machine path defaults from runtime config and pipeline defaults.
- Switched source corpus defaults to `./sample_poems` and env-based configuration.

### Security
- Added explicit guidance to keep secrets and local credentials out of the repository.
