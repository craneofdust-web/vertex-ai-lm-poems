# Vertex AI LM POEMS

Vertex AI powered pipeline for building a Poetry Skill Web from Markdown poem corpora.

Chinese guide: `中文說明.md`

## Versioning

- API package version is currently `0.1.x` (service/runtime release baseline).
- Active runtime data scope is `v0.3` (runs under `runtime_workspaces/` and ingested to SQLite).
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
python scripts/init_db.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

On macOS/Linux, replace `python` with `python3` if needed.

Open:
- `http://127.0.0.1:8010/`
- `http://127.0.0.1:8010/docs`
- `http://127.0.0.1:8010/visualizations` (all available skill-tree indices)
- `http://127.0.0.1:8010/visualization/latest?mode=full` (latest full run, recommended)

## Environment Variables

Copy `.env.example` to `.env` and fill values.

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

# full
python scripts/trigger_api_run.py --mode full --iterations 6 --sample-size 30 --max-stage-jump 2 --out logs/last_full_result.json
```

## Skill Tree Index Entry Points

After backend startup, use these stable routes instead of opening nested files manually:

- `http://127.0.0.1:8010/visualizations` to browse all run indices
- `http://127.0.0.1:8010/visualization/latest?mode=full` to open latest full run
- `http://127.0.0.1:8010/visualization/latest?mode=smoke` to open latest smoke run
- `http://127.0.0.1:8010/visualization/latest?mode=any` to open latest available run
- `http://127.0.0.1:8010/visualization/{run_id}/` to open one specific run index
- `http://127.0.0.1:8010/visualization/{run_id}/{asset_path}` to open visualization assets/files under that run

Note:
- API default scope is active runtime runs (`runtime_workspaces`, v0.3). Legacy/reference snapshots are not used by default routes.
- Visualization routes list/serve only runtime runs that are already ingested into the SQLite DB.
- `V1~V6` labels inside a run index represent visualization style variants, not pipeline versions (`v0.1/v0.2/v0.3`).

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

## Contributing

See `CONTRIBUTING.md`.

## Code of Conduct

See `CODE_OF_CONDUCT.md`.

## Security

See `SECURITY.md`.

## License

MIT. See `LICENSE`.
