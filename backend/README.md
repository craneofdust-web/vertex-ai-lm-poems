# Backend Service

FastAPI + SQLite runtime for graph query, lineage, and pipeline execution.

## Versioning

- API package version: `0.1.x`
- Default runtime data scope: `v0.3.1` (`runtime_workspaces` + ingested SQLite runs)
- Visualization `V1~V6`: style variants only

## Endpoints

- `GET /graph?run_id=...`
- `GET /node/{node_id}?run_id=...`
- `GET /node/{node_id}/lineage?run_id=...`
- `GET /search?q=...&run_id=...`
- `POST /run/smoke`
- `POST /run/full`
- `GET /runs` (active runtime runs only, v0.3.1)
- `GET /runs/{run_id}/audit` (corpus scan vs citation/mounting coverage audit)
- `GET /visualizations` (index of all available visualization entry pages)
- `GET /visualization/latest?mode=full|smoke|any` (redirect to latest visualization entry page by mode)
- `GET /visualization/{run_id}` (redirect to `/visualization/{run_id}/`)
- `GET /visualization/{run_id}/` (visualization entry page for one run)
- `GET /visualization/{run_id}/{asset_path}` (assets/files for one run visualization directory)

Default behavior:
- Endpoints without explicit `run_id` resolve to the latest active runtime run under `runtime_workspaces` (v0.3.1 scope).
- Visualization endpoints only expose runtime runs that are already ingested into SQLite.
- `V1~V6` in visualization pages are style variants only, not pipeline versions.
- `GET /runs` returns per-run `stats`; when ingest metadata exists it includes mounting coverage keys (`mounting_full_*`, `mounting_seed_*`).

## Quick Start

```powershell
# from repository root
cd backend
python -m pip install -r requirements.txt
python scripts/start_local.py --reload
```

On macOS/Linux, replace `python` with `python3` if needed.
Project-root `.env` values are auto-loaded when not already exported in the shell.
`requirements.txt` is runtime-only; install `requirements-pipeline.txt` only when you need `/run/*`.

Dependency files:
- `requirements.txt`: runtime server dependencies
- `requirements-dev.txt`: test and lint dependencies
- `requirements-pipeline.txt`: pipeline generation dependencies (`vertexai`)

Open:
- `http://127.0.0.1:8010/`
- `http://127.0.0.1:8010/docs`

## Troubleshooting

If you see `No module named uvicorn` inside `.venv`, dependencies were not installed in that environment.

Use this fallback setup:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/start_local.py --reload
```

If `pip` reports SSL certificate mismatch for `pypi.org`, fix your network/proxy certificate settings first.

If `/run/smoke` or `/run/full` fails with `Missing dependency: vertexai`, install requirements in the same Python interpreter used to launch backend:

```bash
python3 -m pip install -r requirements-pipeline.txt
```

## Smoke Example

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8010/run/smoke" -ContentType "application/json" -Body "{}"
```

## Full Example

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8010/run/full" -ContentType "application/json" -Body "{}"
```

For 500+ corpora, avoid legacy low-coverage settings such as `iterations=6` and `sample_size=30`.
If you need explicit parameters, prefer a higher baseline (for example `iterations=30`, `sample_size=50`) and adjust from there.

## Optional Progress Monitor

```powershell
powershell -ExecutionPolicy Bypass -File ".\\scripts\\progress_monitor.ps1" -IntervalSec 300
```

## Run Audit Script

```powershell
python scripts/audit_run.py --run-id run_full_20260222_192855 --out logs/run_audit.json
```

## Fill Quality Sampling Script

```powershell
python scripts/sample_fill_quality.py --run-id run_full_20260222_192855 --sample-size 40 --seed 42 --out-prefix logs/fill_quality_192855
```

This script samples `fill_assignments.json` and checks quote-in-source validity before promoting fill matches into citation records.
