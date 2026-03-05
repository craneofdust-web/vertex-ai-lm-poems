# Vertex AI LM POEMS

Vertex AI powered pipeline for building a Poetry Skill Web from Markdown poem corpora.

Chinese guide: `README.zh-TW.md` (entry alias: `中文說明.md`)

## Versioning

- API package version is currently `0.1.x` (service/runtime release baseline).
- Active runtime data scope is `v0.3.1` (runs under `runtime_workspaces/` and ingested to SQLite).
- Visualization labels `V1~V6` are UI style variants, not pipeline versions.

The project supports three layers:
- generation (`brainstorm_skill_webs.py`)
- merge and fill (`build_master_and_fill_mounting.py`)
- API + UI runtime (`backend`)

## Repository Layout

- `brainstorm_skill_webs.py`: generate skill graph fragments from poem samples.
- `build_master_and_fill_mounting.py`: merge fragments and fill unmatched poem-node mappings.
- `generate_skill_tree_visualizations.py`: render visualization HTML from merged graph.
- `backend/`: FastAPI + SQLite runtime and static frontend.
- `runtime_workspaces/`: active API pipeline run outputs.
- `references/`: tracked reference docs (`v0.1_notebookLM/`) plus local-only ignored snapshots (`v0.2_api_results/`, `legacy_handoff/`).
- `recycle_bin/`: quarantine area before permanent deletion.
- `sample_poems/`: local sample corpus folder (tracked as placeholder only).

## Prerequisites

- Python 3.11+
- Google Cloud project with Vertex AI access
- Application Default Credentials or service account credentials

## Quick Start

```powershell
# from repository root
cd backend
python -m pip install -r requirements.txt
python scripts/start_local.py --reload
```

On macOS/Linux, replace `python` with `python3` if needed.
`requirements.txt` only contains runtime dependencies; install `requirements-pipeline.txt` when using `/run/*`.

Open:
- `http://127.0.0.1:8010/`
- `http://127.0.0.1:8010/docs`
- `http://127.0.0.1:8010/visualizations` (all available skill-tree indices)
- `http://127.0.0.1:8010/visualization/latest?mode=full` (latest full run, recommended)

### Recommended Daily Startup (macOS/Linux)

```bash
cd "/Users/liujiugao/Library/CloudStorage/OneDrive-個人/代碼庫與projects/vertex ai LM POEMS"
git pull
cd backend
source .venv/bin/activate
python3 scripts/start_local.py --reload
```

### Startup Troubleshooting (macOS/Linux)

If `pip install` fails with SSL hostname mismatch for `pypi.org` (for example, certificate not matching `pypi.org`), this is a local network/proxy certificate issue, not an API bug.

- Preferred fix: switch to a trusted network or correct your proxy/certificate settings.
- Temporary local fallback (when system Python already has dependencies):

```bash
cd backend
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/start_local.py --reload
```

If you are already inside a broken `.venv`, run `deactivate` first, then retry.

If pipeline endpoints (`/run/smoke`, `/run/full`) fail with `Missing dependency: vertexai`, install requirements in the same interpreter used to start backend:

```bash
cd backend
python3 -m pip install -r requirements-pipeline.txt
```

## Environment Variables

Copy `.env.example` to `.env` and fill values.
`backend/app/config.py` auto-loads project-root `.env` at startup if variables are not already exported in your shell.

Required:
- `PROJECT_ID`
- `POEMS_SOURCE_FOLDER`

Recommended:
- `LOCATION` (default `us-central1`)
- `VERTEX_MODEL_CANDIDATES`
- `MAX_STAGE_JUMP`

Auth:
- `GOOGLE_APPLICATION_CREDENTIALS` (if not using ADC)

## Running Pipeline

From `backend`:

```powershell
# smoke
python scripts/trigger_api_run.py --mode smoke --iterations 2 --sample-size 20 --max-stage-jump 2 --out logs/last_smoke_result.json

# full (v0.3.1 recommended coverage profile)
python scripts/trigger_api_run.py --mode full --max-stage-jump 2 --out logs/last_full_result.json
```

Notes:
- Do not use legacy quick full settings such as `--iterations 6 --sample-size 30` for 500+ corpora. This often under-covers citations.
- If you need explicit full parameters, start from `--iterations 30 --sample-size 50` and tune based on corpus size.

## Skill Tree Index Entry Points

After backend startup, use these stable routes instead of opening nested files manually:

- `http://127.0.0.1:8010/visualizations` to browse all run indices
- `http://127.0.0.1:8010/visualization/latest?mode=full` to open latest full run
- `http://127.0.0.1:8010/visualization/latest?mode=smoke` to open latest smoke run
- `http://127.0.0.1:8010/visualization/latest?mode=any` to open latest available run
- `http://127.0.0.1:8010/visualization/{run_id}/` to open one specific run index
- `http://127.0.0.1:8010/visualization/{run_id}/{asset_path}` to open visualization assets/files under that run

Note:
- API default scope is active runtime runs (`runtime_workspaces`, v0.3.1). Legacy/reference snapshots are not used by default routes.
- Visualization routes list/serve only runtime runs that are already ingested into the SQLite DB.
- `V1~V6` labels inside a run index represent visualization style variants, not pipeline versions (`v0.1/v0.2/v0.3.1`).

## Coverage Audit

Use run audit to distinguish corpus scan coverage vs graph citation coverage.

From `backend`:

```powershell
python scripts/audit_run.py --run-id run_full_20260222_192855 --out logs/run_audit.json
```

API:

- `GET /runs/{run_id}/audit`
- `GET /runs` also includes per-run `stats`; when available it contains mounting coverage fields (`mounting_full_*`, `mounting_seed_*`).

## Fill QA Gate (before promoting fill matches)

For quality gating, sample `fill_assignments.json` and validate whether quoted text exists in original sources:

```powershell
python scripts/sample_fill_quality.py --run-id run_full_20260222_192855 --sample-size 40 --seed 42 --out-prefix logs/fill_quality_192855
```

Outputs:
- `logs/fill_quality_192855.json`
- `logs/fill_quality_192855.md`

Interpretation:
- `full_matches_from_poem_mounting_full` is total full mounting matches.
- `seed_matches_from_poem_mounting_seed` is the initial seed matches.
- `fill_matches_from_fill_assignments` is fill-only (typically `full - seed`).
- Promote fill results into citation records only after sample QA is acceptable.

## Data and Privacy Policy

- Real poem corpora are expected to be local and externalized via `POEMS_SOURCE_FOLDER`.
- Generated runtime outputs are treated as local artifacts and are ignored by default.
- Do not commit secrets, personal paths, or credential files.

## Known Limitations

- No CI pipeline is configured yet.
- API auth/rate limiting is not enabled by default.
- Large corpora and large run histories may require extra storage management.

## Public Publishing Checklist

- Verify repository metadata before publishing:
  - verify `.github/ISSUE_TEMPLATE/config.yml` security reporting link is reachable and intentional.
  - confirm `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, and `PUBLIC_SCOPE.md` are current.
- Confirm no local/private artifacts are tracked:
  - no credentials or `.env` files
  - no runtime outputs (`runtime_workspaces/`, DB files, logs)
  - no personal corpus content
- Run minimum validation:
  - `python -m compileall -q backend/app`
  - start backend and verify `/health`, `/runs`, `/graph`, `/visualizations`

## Improvement Roadmap

- See `IMPROVEMENT_ROADMAP.md` for prioritized frontend/backend follow-up targets and decision-required UI options.

## Contributing

See `CONTRIBUTING.md`.

## Code of Conduct

See `CODE_OF_CONDUCT.md`.

## Security

See `SECURITY.md`.

## License

MIT. See `LICENSE`.
