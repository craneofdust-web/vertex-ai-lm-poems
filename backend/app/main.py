from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import get_settings
from .db import db_session, init_db
from .ingest import ingest_run_artifacts
from .lineage import build_adjacency, walk_ancestors, walk_descendants
from .pipeline import PipelineRequest, run_generation_pipeline


settings = get_settings()
settings.runtime_root.mkdir(parents=True, exist_ok=True)
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
settings.static_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Poetry Skill Web API", version="0.1.0")
ACTIVE_PIPELINE_VERSION = "v0.3"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")


class RunRequestBody(BaseModel):
    project_id: str | None = None
    location: str | None = None
    model_candidates: str | None = None
    iterations: int | None = Field(default=None, ge=1, le=200)
    sample_size: int | None = Field(default=None, ge=1, le=1000)
    max_stage_jump: int | None = Field(default=None, ge=1, le=10)
    source_folder: str | None = None
    skip_fill: bool = False


def _collect_runtime_run_dirs() -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for run_dir in settings.runtime_root.glob("*/runs/*"):
        if not run_dir.is_dir():
            continue
        master_path = run_dir / "master_skill_web.json"
        if not master_path.is_file():
            continue
        index_path = run_dir / "visualizations" / "index.html"
        stat_target = index_path if index_path.is_file() else master_path
        try:
            stat = stat_target.stat()
        except OSError:
            continue
        run_id = run_dir.name
        entry = {
            "run_id": run_id,
            "run_dir": run_dir,
            "master_path": master_path,
            "index_path": index_path if index_path.is_file() else None,
            "mode": (
                "full"
                if run_id.startswith("run_full_")
                else "smoke"
                if run_id.startswith("run_smoke_")
                else "other"
            ),
            "mtime": stat.st_mtime,
        }
        existing = entries.get(run_id)
        if existing is None or float(entry["mtime"]) > float(existing["mtime"]):
            entries[run_id] = entry
    return sorted(entries.values(), key=lambda item: float(item["mtime"]), reverse=True)


def _runtime_run_ids() -> set[str]:
    return {str(item["run_id"]) for item in _collect_runtime_run_dirs()}


def _ingested_runtime_run_ids(conn) -> set[str]:
    runtime_ids = sorted(_runtime_run_ids())
    if not runtime_ids:
        return set()
    placeholders = ",".join("?" for _ in runtime_ids)
    sql = f"SELECT run_id FROM runs WHERE run_id IN ({placeholders})"
    rows = conn.execute(sql, tuple(runtime_ids)).fetchall()
    return {str(row["run_id"]) for row in rows}


def _resolve_latest_runtime_run_id(conn) -> str:
    runtime_entries = _collect_runtime_run_dirs()
    runtime_ids = [str(item["run_id"]) for item in runtime_entries]
    if not runtime_ids:
        raise HTTPException(
            status_code=404,
            detail=f"no active {ACTIVE_PIPELINE_VERSION} runtime runs found under runtime_workspaces",
        )

    ingested_ids = _ingested_runtime_run_ids(conn)
    for preferred_mode in ("full", "smoke", "other"):
        for item in runtime_entries:
            if str(item.get("mode")) != preferred_mode:
                continue
            run_id = str(item["run_id"])
            if run_id in ingested_ids:
                return run_id
    if not ingested_ids:
        raise HTTPException(
            status_code=404,
            detail=f"no active {ACTIVE_PIPELINE_VERSION} runtime runs ingested in database",
        )
    raise HTTPException(
        status_code=404,
        detail=f"no active {ACTIVE_PIPELINE_VERSION} runtime runs with valid artifacts found",
    )


def _resolve_run_id(conn, run_id: str | None) -> str:
    runtime_ids = _runtime_run_ids()
    ingested_ids = _ingested_runtime_run_ids(conn)
    if run_id:
        exists = conn.execute("SELECT 1 FROM runs WHERE run_id = ? LIMIT 1", (run_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
        if run_id not in runtime_ids or run_id not in ingested_ids:
            raise HTTPException(
                status_code=404,
                detail=f"run_id not found in active {ACTIVE_PIPELINE_VERSION} runtime: {run_id}",
            )
        return run_id
    return _resolve_latest_runtime_run_id(conn)


def _node_summary(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "tier": row["tier"],
        "stage": int(row["stage"]),
        "lane": row["lane"],
        "support_count": int(row["support_count"]),
    }


def _collect_visualization_entries(allowed_run_ids: set[str] | None = None) -> list[dict[str, Any]]:
    entries = []
    for item in _collect_runtime_run_dirs():
        run_id = str(item["run_id"])
        if allowed_run_ids is not None and run_id not in allowed_run_ids:
            continue
        index_path = item["index_path"]
        if not isinstance(index_path, Path) or not index_path.is_file():
            continue
        try:
            mtime = float(index_path.stat().st_mtime)
        except OSError:
            continue
        entries.append(
            {
                "run_id": run_id,
                "index_path": index_path,
                "source": "runtime",
                "mode": str(item["mode"]),
                "mtime": mtime,
            }
        )
    return sorted(entries, key=lambda item: float(item["mtime"]), reverse=True)


def _resolve_visualization_entry(
    run_id: str | None = None,
    prefer_mode: str = "full",
    allowed_run_ids: set[str] | None = None,
) -> dict[str, Any]:
    entries = _collect_visualization_entries(allowed_run_ids=allowed_run_ids)
    if not entries:
        raise HTTPException(
            status_code=404,
            detail=f"no {ACTIVE_PIPELINE_VERSION} visualization index found in runtime_workspaces",
        )
    if run_id:
        for entry in entries:
            if entry["run_id"] == run_id:
                return entry
        raise HTTPException(
            status_code=404,
            detail=f"visualization index not found in {ACTIVE_PIPELINE_VERSION} runtime: {run_id}",
        )
    if prefer_mode in {"full", "smoke"}:
        for entry in entries:
            if entry["mode"] == prefer_mode:
                return entry
    return entries[0]


def _collect_runs_missing_visualization(allowed_run_ids: set[str] | None = None) -> list[dict[str, Any]]:
    items = []
    for item in _collect_runtime_run_dirs():
        run_id = str(item["run_id"])
        if allowed_run_ids is not None and run_id not in allowed_run_ids:
            continue
        if isinstance(item["index_path"], Path):
            continue
        items.append(
            {
                "run_id": run_id,
                "source": "runtime",
                "mtime": float(item["mtime"]),
            }
        )
    return sorted(items, key=lambda item: float(item["mtime"]), reverse=True)


def _visualization_url(run_id: str, asset_path: str | None = None) -> str:
    run_segment = quote(run_id, safe="")
    if asset_path:
        return f"/visualization/{run_segment}/{quote(asset_path, safe='/')}"
    return f"/visualization/{run_segment}/"


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def root() -> FileResponse:
    return FileResponse(settings.static_dir / "index.html")


@app.get("/visualization/latest")
def latest_visualization_index(mode: str = Query("full")) -> RedirectResponse:
    normalized = mode.strip().lower()
    if normalized not in {"full", "smoke", "any"}:
        raise HTTPException(status_code=400, detail="mode must be one of: full, smoke, any")
    with db_session() as conn:
        allowed_run_ids = _ingested_runtime_run_ids(conn)
    entry = _resolve_visualization_entry(prefer_mode=normalized, allowed_run_ids=allowed_run_ids)
    return RedirectResponse(url=_visualization_url(str(entry["run_id"])), status_code=307)


@app.get("/visualization/{run_id}")
def visualization_index_redirect(run_id: str) -> RedirectResponse:
    with db_session() as conn:
        allowed_run_ids = _ingested_runtime_run_ids(conn)
    _resolve_visualization_entry(run_id=run_id, allowed_run_ids=allowed_run_ids)
    return RedirectResponse(url=_visualization_url(run_id), status_code=307)


@app.get("/visualization/{run_id}/")
def visualization_index_by_run(run_id: str) -> FileResponse:
    with db_session() as conn:
        allowed_run_ids = _ingested_runtime_run_ids(conn)
    entry = _resolve_visualization_entry(run_id=run_id, allowed_run_ids=allowed_run_ids)
    return FileResponse(entry["index_path"])


@app.get("/visualization/{run_id}/{asset_path:path}")
def visualization_asset_by_run(run_id: str, asset_path: str) -> FileResponse:
    if not asset_path or asset_path == "/":
        return visualization_index_by_run(run_id)
    with db_session() as conn:
        allowed_run_ids = _ingested_runtime_run_ids(conn)
    entry = _resolve_visualization_entry(run_id=run_id, allowed_run_ids=allowed_run_ids)
    visualization_dir = Path(entry["index_path"]).parent.resolve()
    asset_file = (visualization_dir / asset_path).resolve()
    try:
        asset_file.relative_to(visualization_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid visualization asset path") from exc
    if not asset_file.is_file():
        raise HTTPException(status_code=404, detail=f"visualization asset not found: {asset_path}")
    return FileResponse(asset_file)


@app.get("/visualizations")
def visualizations_index() -> HTMLResponse:
    with db_session() as conn:
        allowed_run_ids = _ingested_runtime_run_ids(conn)
    entries = _collect_visualization_entries(allowed_run_ids=allowed_run_ids)
    if not entries:
        raise HTTPException(
            status_code=404,
            detail=f"no {ACTIVE_PIPELINE_VERSION} visualization index found in runtime_workspaces",
        )
    missing = _collect_runs_missing_visualization(allowed_run_ids=allowed_run_ids)

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
        run_href = escape(_visualization_url(run_id_raw))
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
        "not pipeline versions like <code>v0.1/v0.2/v0.3</code>.</p>"
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


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "pipeline_version": ACTIVE_PIPELINE_VERSION,
    }


@app.get("/graph")
def get_graph(run_id: str | None = None, include_weak: bool = False) -> dict[str, Any]:
    with db_session() as conn:
        resolved_run_id = _resolve_run_id(conn, run_id)
        node_rows = conn.execute(
            """
            SELECT id, name, tier, stage, lane, support_count
            FROM nodes
            WHERE run_id = ?
            ORDER BY stage ASC, support_count DESC, id ASC
            """,
            (resolved_run_id,),
        ).fetchall()

        edge_sql = """
            SELECT source_id, target_id, edge_type, is_direct, stage_jump
            FROM edges
            WHERE run_id = ?
        """
        params: list[Any] = [resolved_run_id]
        if not include_weak:
            edge_sql += " AND edge_type = 'primary' AND is_direct = 1"
        edge_sql += " ORDER BY target_id ASC, edge_type ASC, source_id ASC"
        edge_rows = conn.execute(edge_sql, tuple(params)).fetchall()

        return {
            "run_id": resolved_run_id,
            "nodes": [_node_summary(row) for row in node_rows],
            "edges": [
                {
                    "source_id": row["source_id"],
                    "target_id": row["target_id"],
                    "edge_type": row["edge_type"],
                    "is_direct": int(row["is_direct"]),
                    "stage_jump": int(row["stage_jump"]),
                }
                for row in edge_rows
            ],
            "meta": {
                "node_count": len(node_rows),
                "edge_count": len(edge_rows),
                "include_weak": include_weak,
                "pipeline_version": ACTIVE_PIPELINE_VERSION,
            },
        }


@app.get("/node/{node_id}")
def get_node(node_id: str, run_id: str | None = None) -> dict[str, Any]:
    with db_session() as conn:
        resolved_run_id = _resolve_run_id(conn, run_id)
        node = conn.execute(
            """
            SELECT id, name, tier, stage, lane, description, unlock_condition, support_count
            FROM nodes
            WHERE run_id = ? AND id = ?
            """,
            (resolved_run_id, node_id),
        ).fetchone()
        if not node:
            raise HTTPException(status_code=404, detail=f"node not found: {node_id}")

        citations = conn.execute(
            """
            SELECT source_id, source_title, quote, why, folder_status
            FROM citations
            WHERE run_id = ? AND node_id = ?
            ORDER BY id ASC
            """,
            (resolved_run_id, node_id),
        ).fetchall()

        primary = conn.execute(
            """
            SELECT e.source_id, n.name, n.tier, n.stage, e.stage_jump, e.is_direct
            FROM edges e
            JOIN nodes n ON n.run_id = e.run_id AND n.id = e.source_id
            WHERE e.run_id = ? AND e.target_id = ? AND e.edge_type = 'primary'
            ORDER BY e.id ASC
            LIMIT 1
            """,
            (resolved_run_id, node_id),
        ).fetchone()

        weak = conn.execute(
            """
            SELECT e.source_id, n.name, n.tier, n.stage, e.stage_jump, e.is_direct
            FROM edges e
            JOIN nodes n ON n.run_id = e.run_id AND n.id = e.source_id
            WHERE e.run_id = ? AND e.target_id = ? AND e.edge_type = 'weak'
            ORDER BY n.stage ASC, n.name ASC
            """,
            (resolved_run_id, node_id),
        ).fetchall()

        downstream = conn.execute(
            """
            SELECT DISTINCT n.id, n.name, n.tier, n.stage, n.lane, n.support_count
            FROM edges e
            JOIN nodes n ON n.run_id = e.run_id AND n.id = e.target_id
            WHERE e.run_id = ? AND e.source_id = ?
            ORDER BY n.stage ASC, n.support_count DESC, n.id ASC
            """,
            (resolved_run_id, node_id),
        ).fetchall()

        return {
            "run_id": resolved_run_id,
            "node": {
                "id": node["id"],
                "name": node["name"],
                "tier": node["tier"],
                "stage": int(node["stage"]),
                "lane": node["lane"],
                "description": node["description"],
                "unlock_condition": node["unlock_condition"],
                "support_count": int(node["support_count"]),
            },
            "semantics": {
                "primary_link": "single strongest prerequisite edge for canvas rendering",
                "weak_relations": "other prerequisites kept in sidebar by default",
                "immediate_downstream": "nodes that directly depend on current node",
            },
            "primary_link": (
                {
                    "source_id": primary["source_id"],
                    "source_name": primary["name"],
                    "source_tier": primary["tier"],
                    "source_stage": int(primary["stage"]),
                    "stage_jump": int(primary["stage_jump"]),
                    "is_direct": int(primary["is_direct"]),
                }
                if primary
                else None
            ),
            "weak_relations": [
                {
                    "source_id": row["source_id"],
                    "source_name": row["name"],
                    "source_tier": row["tier"],
                    "source_stage": int(row["stage"]),
                    "stage_jump": int(row["stage_jump"]),
                    "is_direct": int(row["is_direct"]),
                }
                for row in weak
            ],
            "immediate_downstream": [_node_summary(row) for row in downstream],
            "citations": [
                {
                    "source_id": row["source_id"],
                    "source_title": row["source_title"],
                    "quote": row["quote"],
                    "why": row["why"],
                    "folder_status": row["folder_status"],
                }
                for row in citations
            ],
        }


@app.get("/node/{node_id}/lineage")
def get_lineage(node_id: str, run_id: str | None = None) -> dict[str, Any]:
    with db_session() as conn:
        resolved_run_id = _resolve_run_id(conn, run_id)
        node_row = conn.execute(
            """
            SELECT id, name, tier, stage, lane, support_count
            FROM nodes
            WHERE run_id = ? AND id = ?
            """,
            (resolved_run_id, node_id),
        ).fetchone()
        if not node_row:
            raise HTTPException(status_code=404, detail=f"node not found: {node_id}")

        edges = conn.execute(
            """
            SELECT source_id, target_id
            FROM edges
            WHERE run_id = ?
            """,
            (resolved_run_id,),
        ).fetchall()
        upstream_map, downstream_map = build_adjacency([dict(row) for row in edges])
        ancestor_ids = walk_ancestors(node_id, upstream_map)
        descendant_ids = walk_descendants(node_id, downstream_map)

        all_nodes = conn.execute(
            """
            SELECT id, name, tier, stage, lane, support_count
            FROM nodes
            WHERE run_id = ?
            """,
            (resolved_run_id,),
        ).fetchall()
        node_by_id = {row["id"]: row for row in all_nodes}

        upstream = [_node_summary(node_by_id[item]) for item in sorted(ancestor_ids) if item in node_by_id]
        upstream.sort(key=lambda item: (item["stage"], -item["support_count"], item["id"]))

        stage = int(node_row["stage"])
        midstream = [
            _node_summary(row)
            for row in all_nodes
            if int(row["stage"]) == stage
        ]
        midstream.sort(key=lambda item: (-item["support_count"], item["id"]))

        downstream = [
            _node_summary(node_by_id[item]) for item in sorted(descendant_ids) if item in node_by_id
        ]
        downstream.sort(key=lambda item: (item["stage"], -item["support_count"], item["id"]))

        return {
            "run_id": resolved_run_id,
            "node": _node_summary(node_row),
            "lineage": {
                "upstream": upstream,
                "midstream": midstream,
                "downstream": downstream,
            },
        }


@app.get("/search")
def search(q: str = Query(..., min_length=1), run_id: str | None = None, limit: int = 20) -> dict[str, Any]:
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="query cannot be blank")
    with db_session() as conn:
        resolved_run_id = _resolve_run_id(conn, run_id)
        pattern = f"%{q}%"
        capped = max(1, min(limit, 100))
        node_rows = conn.execute(
            """
            SELECT id, name, tier, stage, lane, support_count
            FROM nodes
            WHERE run_id = ?
              AND (id LIKE ? OR name LIKE ? OR description LIKE ? OR unlock_condition LIKE ?)
            ORDER BY support_count DESC, stage ASC, id ASC
            LIMIT ?
            """,
            (resolved_run_id, pattern, pattern, pattern, pattern, capped),
        ).fetchall()
        source_rows = conn.execute(
            """
            SELECT source_id, title
            FROM sources
            WHERE run_id = ?
              AND (source_id LIKE ? OR title LIKE ? OR text LIKE ?)
            ORDER BY title ASC, source_id ASC
            LIMIT ?
            """,
            (resolved_run_id, pattern, pattern, pattern, capped),
        ).fetchall()
        return {
            "run_id": resolved_run_id,
            "query": q,
            "nodes": [_node_summary(row) for row in node_rows],
            "sources": [
                {"source_id": row["source_id"], "title": row["title"]} for row in source_rows
            ],
        }


def _run_and_ingest(mode: str, body: RunRequestBody) -> dict[str, Any]:
    project_id = body.project_id or settings.default_project_id
    location = body.location or settings.default_location
    model_candidates = body.model_candidates or settings.default_model_candidates
    max_stage_jump = int(body.max_stage_jump or settings.default_max_stage_jump)
    source_folder = Path(body.source_folder).expanduser() if body.source_folder else settings.source_folder

    pipeline_result = run_generation_pipeline(
        settings,
        PipelineRequest(
            mode=mode,
            project_id=project_id,
            location=location,
            model_candidates=model_candidates,
            max_stage_jump=max_stage_jump,
            iterations=body.iterations,
            sample_size=body.sample_size,
            skip_fill=body.skip_fill,
            source_folder=source_folder,
        ),
    )
    run_id = str(pipeline_result["run_id"])
    run_dir = Path(str(pipeline_result["run_dir"]))

    with db_session() as conn:
        selected_models = pipeline_result.get("selected_models", {}) or {}
        resolved_model_used = str(selected_models.get("model_used") or "").strip()
        if not resolved_model_used:
            resolved_model_used = model_candidates.split(",")[0].strip()
        ingest_result = ingest_run_artifacts(
            conn=conn,
            run_id=run_id,
            run_dir=run_dir,
            source_folder=source_folder,
            model_used=resolved_model_used,
            iterations=pipeline_result.get("iterations"),
            sample_size=pipeline_result.get("sample_size"),
            max_stage_jump=max_stage_jump,
            config={
                "pipeline_version": ACTIVE_PIPELINE_VERSION,
                "mode": mode,
                "project_id": project_id,
                "location": location,
                "model_candidates": model_candidates,
                "selected_models": selected_models,
                "pipeline": pipeline_result.get("commands", []),
            },
        )

    return {
        "pipeline": pipeline_result,
        "ingest": ingest_result,
    }


@app.post("/run/smoke")
def run_smoke(body: RunRequestBody | None = None) -> dict[str, Any]:
    payload = body or RunRequestBody()
    if payload.iterations is None:
        payload.iterations = 2
    if payload.sample_size is None:
        payload.sample_size = 20
    payload.skip_fill = True
    return _run_and_ingest("smoke", payload)


@app.post("/run/full")
def run_full(body: RunRequestBody | None = None) -> dict[str, Any]:
    payload = body or RunRequestBody()
    return _run_and_ingest("full", payload)


@app.get("/runs")
def list_runs(limit: int = 30) -> dict[str, Any]:
    with db_session() as conn:
        runtime_entries = _collect_runtime_run_dirs()
        runtime_ids = [str(item["run_id"]) for item in runtime_entries]
        capped = max(1, min(limit, 200))
        if not runtime_ids:
            return {"pipeline_version": ACTIVE_PIPELINE_VERSION, "runs": []}
        placeholders = ",".join("?" for _ in runtime_ids)
        sql = (
            "SELECT run_id, created_at, model_used, iterations, sample_size, config_json "
            "FROM runs "
            f"WHERE run_id IN ({placeholders})"
        )
        rows = conn.execute(sql, tuple(runtime_ids)).fetchall()
        rows_by_id = {str(row["run_id"]): row for row in rows}

        ordered_rows = []
        for preferred_mode in ("full", "smoke", "other"):
            for item in runtime_entries:
                if str(item.get("mode")) != preferred_mode:
                    continue
                row = rows_by_id.get(str(item["run_id"]))
                if row is not None:
                    ordered_rows.append(row)
                if len(ordered_rows) >= capped:
                    break
            if len(ordered_rows) >= capped:
                break

        out = []
        for row in ordered_rows:
            item = {
                "run_id": row["run_id"],
                "created_at": row["created_at"],
                "model_used": row["model_used"],
                "iterations": row["iterations"],
                "sample_size": row["sample_size"],
                "pipeline_version": ACTIVE_PIPELINE_VERSION,
            }
            if row["config_json"]:
                try:
                    item["config"] = json.loads(row["config_json"])
                except json.JSONDecodeError:
                    item["config"] = {}
            out.append(item)
        return {"pipeline_version": ACTIVE_PIPELINE_VERSION, "runs": out}
