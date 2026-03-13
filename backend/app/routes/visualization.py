from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from ..config import get_settings
from ..constants import ACTIVE_PIPELINE_VERSION
from ..db import db_session
from ..services import run_service


router = APIRouter()
settings = get_settings()


@router.api_route("/visualization/latest", methods=["GET", "HEAD"])
def latest_visualization_index(mode: str = Query("full")) -> RedirectResponse:
    normalized = mode.strip().lower()
    if normalized not in {"full", "smoke", "any"}:
        raise HTTPException(status_code=400, detail="mode must be one of: full, smoke, any")
    with db_session() as conn:
        allowed_run_ids = run_service.ingested_runtime_run_ids(conn, settings)
    entry = run_service.resolve_visualization_entry(
        settings=settings,
        active_pipeline_version=ACTIVE_PIPELINE_VERSION,
        prefer_mode=normalized,
        allowed_run_ids=allowed_run_ids,
    )
    return RedirectResponse(url=run_service.visualization_url(str(entry["run_id"])), status_code=307)


@router.api_route("/visualization/{run_id}", methods=["GET", "HEAD"])
def visualization_index_redirect(run_id: str) -> RedirectResponse:
    with db_session() as conn:
        allowed_run_ids = run_service.ingested_runtime_run_ids(conn, settings)
    run_service.resolve_visualization_entry(
        settings=settings,
        active_pipeline_version=ACTIVE_PIPELINE_VERSION,
        run_id=run_id,
        allowed_run_ids=allowed_run_ids,
    )
    return RedirectResponse(url=run_service.visualization_url(run_id), status_code=307)


@router.api_route("/visualization/{run_id}/", methods=["GET", "HEAD"])
def visualization_index_by_run(run_id: str) -> FileResponse:
    with db_session() as conn:
        allowed_run_ids = run_service.ingested_runtime_run_ids(conn, settings)
    entry = run_service.resolve_visualization_entry(
        settings=settings,
        active_pipeline_version=ACTIVE_PIPELINE_VERSION,
        run_id=run_id,
        allowed_run_ids=allowed_run_ids,
    )
    return FileResponse(entry["index_path"])


@router.api_route("/visualization/{run_id}/{asset_path:path}", methods=["GET", "HEAD"])
def visualization_asset_by_run(run_id: str, asset_path: str) -> FileResponse:
    if not asset_path or asset_path == "/":
        return visualization_index_by_run(run_id)
    with db_session() as conn:
        allowed_run_ids = run_service.ingested_runtime_run_ids(conn, settings)
    entry = run_service.resolve_visualization_entry(
        settings=settings,
        active_pipeline_version=ACTIVE_PIPELINE_VERSION,
        run_id=run_id,
        allowed_run_ids=allowed_run_ids,
    )
    visualization_dir = Path(entry["index_path"]).parent.resolve()
    asset_file = (visualization_dir / asset_path).resolve()
    try:
        asset_file.relative_to(visualization_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid visualization asset path") from exc
    if not asset_file.is_file():
        raise HTTPException(status_code=404, detail=f"visualization asset not found: {asset_path}")
    return FileResponse(asset_file)


@router.api_route("/visualizations", methods=["GET", "HEAD"])
def visualizations_index() -> HTMLResponse:
    with db_session() as conn:
        allowed_run_ids = run_service.ingested_runtime_run_ids(conn, settings)
    entries = run_service.collect_visualization_entries(settings, allowed_run_ids=allowed_run_ids)
    if not entries:
        raise HTTPException(
            status_code=404,
            detail=f"no {ACTIVE_PIPELINE_VERSION} visualization index found in runtime_workspaces",
        )
    missing = run_service.collect_runs_missing_visualization(settings, allowed_run_ids=allowed_run_ids)

    latest_any = entries[0]
    latest_full = next((item for item in entries if item["mode"] == "full"), None)
    latest_smoke = next((item for item in entries if item["mode"] == "smoke"), None)

    latest_any_run_id = escape(str(latest_any["run_id"]))
    latest_full_run_id = escape(str(latest_full["run_id"])) if latest_full else "N/A"
    latest_smoke_run_id = escape(str(latest_smoke["run_id"])) if latest_smoke else "N/A"

    rows = []
    for item in entries:
        run_id_raw = str(item["run_id"])
        run_id = escape(run_id_raw)
        run_href = escape(run_service.visualization_url(run_id_raw))
        source = escape(str(item["source"]))
        mode = escape(str(item["mode"]))
        updated_at = datetime.fromtimestamp(float(item["mtime"])).strftime("%Y-%m-%d %H:%M:%S")
        rows.append(
            f'<li><a href="{run_href}">{run_id}</a> '
            f'| type {mode} | updated {escape(updated_at)} | source {source}</li>'
        )

    missing_rows = []
    for item in missing:
        run_id = escape(str(item["run_id"]))
        source = escape(str(item["source"]))
        updated_at = datetime.fromtimestamp(float(item["mtime"])).strftime("%Y-%m-%d %H:%M:%S")
        missing_rows.append(
            f"<li>{run_id} | updated {escape(updated_at)} | source {source}</li>"
        )

    html = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8' />"
        "<meta name='viewport' content='width=device-width, initial-scale=1' />"
        "<title>Skill Tree Visualization Index</title>"
        "<style>"
        "body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f9fc;color:#17212b;}"
        "h1{margin:0 0 8px 0;} p{margin:6px 0 12px 0;}"
        "a{color:#0b57d0;text-decoration:none;} a:hover{text-decoration:underline;}"
        "ul{padding-left:18px;line-height:1.8;}"
        "code{background:#eef3fd;padding:2px 6px;border-radius:6px;}"
        "</style></head><body>"
        "<h1>Poetry Skill Tree Visualizations</h1>"
        f"<p><strong>Active pipeline:</strong> <code>{ACTIVE_PIPELINE_VERSION}</code> "
        "(runtime_workspaces only)</p>"
        "<p><strong>Note:</strong> <code>V1~V6</code> means visualization styles, "
        "not pipeline versions like <code>v0.1/v0.2/v0.3.1</code>.</p>"
        f"<p>Latest any: <code>{latest_any_run_id}</code> | "
        "<a href='/visualization/latest?mode=any'>open</a></p>"
        f"<p>Latest full: <code>{latest_full_run_id}</code> | "
        "<a href='/visualization/latest?mode=full'>open</a></p>"
        f"<p>Latest smoke: <code>{latest_smoke_run_id}</code> | "
        "<a href='/visualization/latest?mode=smoke'>open</a></p>"
        "<ul>"
        + "".join(rows)
        + "</ul>"
        + "<h2>Runs Missing Visualization Index</h2><ul>"
        + ("".join(missing_rows) if missing_rows else "<li>none</li>")
        + "</ul></body></html>"
    )
    return HTMLResponse(content=html)
