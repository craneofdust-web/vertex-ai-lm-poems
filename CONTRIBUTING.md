# Contributing

Thanks for contributing.

## Development Setup

```powershell
cd backend
python -m pip install -r requirements.txt
python scripts/start_local.py --reload
```

On macOS/Linux, replace `python` with `python3` if needed.

## Local Validation

Run at least one local validation path before opening a PR.

Option A (offline, no Vertex call):

```powershell
python -m compileall -q backend/app
```

Option B (runtime smoke with your configured environment):

```powershell
cd backend
python scripts/trigger_api_run.py --mode smoke --iterations 1 --sample-size 10 --max-stage-jump 2 --out logs/smoke_check.json
```

## Pull Request Rules

- Keep changes scoped and explain impact in PR description.
- Do not commit secrets, local paths, or generated runtime workspaces.
- Update docs (`README.md`, `backend/README.md`) when behavior changes.
- Update `CHANGELOG.md` when user-facing behavior changes.
- Follow `CODE_OF_CONDUCT.md` in all collaboration channels.

## Scope and Versioning

- Default runtime scope is `v0.3` (`runtime_workspaces` + ingested SQLite runs).
- `V1~V6` in visualization pages are style variants only.

## Issue Labels

Recommended starter labels:
- `bug`
- `enhancement`
- `good first issue`
