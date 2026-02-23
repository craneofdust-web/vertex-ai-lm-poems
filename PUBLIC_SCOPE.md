# Public Scope

This file defines what should and should not be published from this repository.

## Public (in-scope)

- Core pipeline code in repository root (`brainstorm_skill_webs.py`, `build_master_and_fill_mounting.py`, `generate_skill_tree_visualizations.py`).
- Runtime API and UI under `backend/`.
- Documentation and templates (`README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `.github/`).
- Placeholder corpus folder `sample_poems/`.

## Private or Local-Only (out-of-scope)

- Personal poem corpus path referenced by local `POEMS_SOURCE_FOLDER`.
- Any `*notebookLM/` reference materials until redistribution rights are explicitly confirmed.
- Generated outputs and run artifacts (`runtime_workspaces/`, `recycle_bin/`, `references/v0.2_api_results/runs/`).
- Local logs and database files.
- Credentials and key material.

## Public Release Rules

- Default public runtime behavior must stay in `v0.3.1` scope (`runtime_workspaces` + ingested DB runs).
- `V1~V6` naming in visualization pages must be described as style variants only.
- Before publishing, verify `.github/ISSUE_TEMPLATE/config.yml` points to the correct repository security policy URL.
