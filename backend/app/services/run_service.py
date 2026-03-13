from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException

from ..ingest import count_markdown_files


def collect_runtime_run_dirs(settings) -> list[dict[str, Any]]:
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


def runtime_run_ids(settings) -> set[str]:
    return {str(item["run_id"]) for item in collect_runtime_run_dirs(settings)}


def runtime_run_dir_by_id(settings, run_id: str) -> Path | None:
    for item in collect_runtime_run_dirs(settings):
        if str(item["run_id"]) == run_id:
            run_dir = item.get("run_dir")
            if isinstance(run_dir, Path):
                return run_dir
    return None


def ingested_runtime_run_ids(conn, settings) -> set[str]:
    runtime_ids = sorted(runtime_run_ids(settings))
    if not runtime_ids:
        return set()
    placeholders = ",".join("?" for _ in runtime_ids)
    sql = f"SELECT run_id FROM runs WHERE run_id IN ({placeholders})"
    rows = conn.execute(sql, tuple(runtime_ids)).fetchall()
    return {str(row["run_id"]) for row in rows}


def resolve_latest_runtime_run_id(conn, settings, active_pipeline_version: str) -> str:
    runtime_entries = collect_runtime_run_dirs(settings)
    runtime_ids = [str(item["run_id"]) for item in runtime_entries]
    if not runtime_ids:
        raise HTTPException(
            status_code=404,
            detail=(
                f"no active {active_pipeline_version} runtime runs found under runtime_workspaces"
            ),
        )

    ingested_ids = ingested_runtime_run_ids(conn, settings)
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
            detail=f"no active {active_pipeline_version} runtime runs ingested in database",
        )
    raise HTTPException(
        status_code=404,
        detail=(
            f"no active {active_pipeline_version} runtime runs with valid artifacts found"
        ),
    )


def resolve_run_id(conn, settings, run_id: str | None, active_pipeline_version: str) -> str:
    runtime_ids = runtime_run_ids(settings)
    ingested_ids = ingested_runtime_run_ids(conn, settings)
    if run_id:
        exists = conn.execute("SELECT 1 FROM runs WHERE run_id = ? LIMIT 1", (run_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
        if run_id not in runtime_ids or run_id not in ingested_ids:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"run_id not found in active {active_pipeline_version} runtime: {run_id}"
                ),
            )
        return run_id
    return resolve_latest_runtime_run_id(conn, settings, active_pipeline_version)


def collect_visualization_entries(
    settings,
    allowed_run_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    entries = []
    for item in collect_runtime_run_dirs(settings):
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


def resolve_visualization_entry(
    settings,
    active_pipeline_version: str,
    run_id: str | None = None,
    prefer_mode: str = "full",
    allowed_run_ids: set[str] | None = None,
) -> dict[str, Any]:
    entries = collect_visualization_entries(settings, allowed_run_ids=allowed_run_ids)
    if not entries:
        raise HTTPException(
            status_code=404,
            detail=(
                f"no {active_pipeline_version} visualization index found in runtime_workspaces"
            ),
        )
    if run_id:
        for entry in entries:
            if entry["run_id"] == run_id:
                return entry
        raise HTTPException(
            status_code=404,
            detail=(
                f"visualization index not found in {active_pipeline_version} runtime: {run_id}"
            ),
        )
    if prefer_mode in {"full", "smoke"}:
        for entry in entries:
            if entry["mode"] == prefer_mode:
                return entry
    return entries[0]


def collect_runs_missing_visualization(
    settings,
    allowed_run_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    items = []
    for item in collect_runtime_run_dirs(settings):
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


def visualization_url(run_id: str, asset_path: str | None = None) -> str:
    run_segment = quote(run_id, safe="")
    if asset_path:
        return f"/visualization/{run_segment}/{quote(asset_path, safe='/')}"
    return f"/visualization/{run_segment}/"


def list_runs(conn, settings, active_pipeline_version: str, limit: int = 30) -> dict[str, Any]:
    runtime_entries = collect_runtime_run_dirs(settings)
    runtime_ids = [str(item["run_id"]) for item in runtime_entries]
    capped = max(1, min(limit, 200))
    if not runtime_ids:
        return {"pipeline_version": active_pipeline_version, "runs": []}
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

    ordered_run_ids = [str(row["run_id"]) for row in ordered_rows]
    if not ordered_run_ids:
        return {"pipeline_version": active_pipeline_version, "runs": []}

    ordered_placeholders = ",".join("?" for _ in ordered_run_ids)
    node_rows = conn.execute(
        f"SELECT run_id, COUNT(*) AS count FROM nodes WHERE run_id IN ({ordered_placeholders}) GROUP BY run_id",
        tuple(ordered_run_ids),
    ).fetchall()
    citation_rows = conn.execute(
        f"SELECT run_id, COUNT(*) AS count FROM citations WHERE run_id IN ({ordered_placeholders}) GROUP BY run_id",
        tuple(ordered_run_ids),
    ).fetchall()
    source_rows = conn.execute(
        (
            "SELECT run_id, COUNT(*) AS total_sources, "
            "SUM(CASE WHEN COALESCE(text, '') <> '' THEN 1 ELSE 0 END) AS sources_with_text "
            f"FROM sources WHERE run_id IN ({ordered_placeholders}) GROUP BY run_id"
        ),
        tuple(ordered_run_ids),
    ).fetchall()

    node_counts = {str(row["run_id"]): int(row["count"]) for row in node_rows}
    citation_counts = {str(row["run_id"]): int(row["count"]) for row in citation_rows}
    source_counts = {str(row["run_id"]): int(row["total_sources"]) for row in source_rows}
    source_with_text_counts = {
        str(row["run_id"]): int(row["sources_with_text"] or 0) for row in source_rows
    }

    out = []
    corpus_count_cache: dict[str, int] = {}
    for row in ordered_rows:
        config: dict[str, Any] = {}
        item = {
            "run_id": row["run_id"],
            "created_at": row["created_at"],
            "model_used": row["model_used"],
            "iterations": row["iterations"],
            "sample_size": row["sample_size"],
            "pipeline_version": active_pipeline_version,
        }
        if row["config_json"]:
            try:
                config = json.loads(row["config_json"])
            except json.JSONDecodeError:
                config = {}
        if config:
            item["config"] = config

        run_id = str(row["run_id"])
        total_sources = int(source_counts.get(run_id, 0))
        sources_with_text = int(source_with_text_counts.get(run_id, 0))
        ingest_stats = config.get("ingest_stats", {}) if isinstance(config, dict) else {}
        source_folder = str(config.get("source_folder", "")).strip()

        corpus_markdown_files = int(ingest_stats.get("corpus_markdown_files", 0) or 0)
        if corpus_markdown_files <= 0 and source_folder:
            cached_count = corpus_count_cache.get(source_folder)
            if cached_count is None:
                cached_count = count_markdown_files(Path(source_folder).expanduser())
                corpus_count_cache[source_folder] = cached_count
            corpus_markdown_files = int(cached_count)

        source_coverage_percent = float(ingest_stats.get("source_coverage_percent", 0.0) or 0.0)
        if source_coverage_percent <= 0 and corpus_markdown_files > 0:
            source_coverage_percent = round((total_sources * 100.0) / corpus_markdown_files, 2)

        stats = {
            "nodes": int(node_counts.get(run_id, 0)),
            "citations": int(citation_counts.get(run_id, 0)),
            "sources": total_sources,
            "sources_with_text": sources_with_text,
            "sources_without_text": max(0, total_sources - sources_with_text),
            "corpus_markdown_files": corpus_markdown_files,
            "source_coverage_percent": source_coverage_percent,
        }
        for key in (
            "mounting_full_poems_total",
            "mounting_full_poems_with_match",
            "mounting_full_poems_without_match",
            "mounting_full_match_coverage_percent",
            "mounting_full_total_matches",
            "mounting_full_avg_match_count",
            "mounting_seed_poems_total",
            "mounting_seed_poems_with_match",
            "mounting_seed_poems_without_match",
            "mounting_seed_match_coverage_percent",
            "mounting_seed_total_matches",
            "mounting_seed_avg_match_count",
        ):
            if key in ingest_stats:
                stats[key] = ingest_stats.get(key)
        item["stats"] = stats
        out.append(item)

    return {"pipeline_version": active_pipeline_version, "runs": out}
