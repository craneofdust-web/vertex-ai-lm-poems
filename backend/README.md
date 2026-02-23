# Backend Service

FastAPI + SQLite runtime for graph query, lineage, and pipeline execution.

## Versioning

- API package version: `0.1.x`
- Default runtime data scope: `v0.3` (`runtime_workspaces` + ingested SQLite runs)
- Visualization `V1~V6`: style variants only

## Endpoints

- `GET /graph?run_id=...`
- `GET /node/{node_id}?run_id=...`
- `GET /node/{node_id}/lineage?run_id=...`
- `GET /search?q=...&run_id=...`
- `POST /run/smoke`
- `POST /run/full`
- `GET /runs` (active runtime runs only, v0.3)
- `GET /visualizations` (index of all available visualization entry pages)
- `GET /visualization/latest?mode=full|smoke|any` (redirect to latest visualization entry page by mode)
- `GET /visualization/{run_id}` (redirect to `/visualization/{run_id}/`)
- `GET /visualization/{run_id}/` (visualization entry page for one run)
- `GET /visualization/{run_id}/{asset_path}` (assets/files for one run visualization directory)

Default behavior:
- Endpoints without explicit `run_id` resolve to the latest active runtime run under `runtime_workspaces` (v0.3 scope).
- Visualization endpoints only expose runtime runs that are already ingested into SQLite.
- `V1~V6` in visualization pages are style variants only, not pipeline versions.

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

## Smoke Example

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8010/run/smoke" -ContentType "application/json" -Body "{}"
```

## Full Example

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8010/run/full" -ContentType "application/json" -Body "{}"
```

## Optional Progress Monitor

```powershell
powershell -ExecutionPolicy Bypass -File ".\\scripts\\progress_monitor.ps1" -IntervalSec 300
```
