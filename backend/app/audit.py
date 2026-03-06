from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ingest import count_markdown_files


def _sanitize_legacy_path_text(text: str) -> str:
    out = str(text)
    out = out.replace("\\next_window_stack\\", "\\")
    out = out.replace("/next_window_stack/", "/")
    return out


def _sanitize_legacy_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_legacy_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_legacy_paths(item) for item in value]
    if isinstance(value, str):
        return _sanitize_legacy_path_text(value)
    return value


def _read_json_if_exists(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _mounting_summary(rows: Any) -> dict[str, Any]:
    if not isinstance(rows, list) or not rows:
        return {
            "poems_total": 0,
            "poems_with_match": 0,
            "poems_without_match": 0,
            "match_coverage_percent": 0.0,
            "total_matches": 0,
            "avg_match_count": 0.0,
            "min_match_count": 0,
            "max_match_count": 0,
            "multi_match_poems": 0,
        }

    match_counts: list[int] = []
    for row in rows:
        if not isinstance(row, dict):
            match_counts.append(0)
            continue
        raw = row.get("match_count")
        if raw is None:
            nodes = row.get("matched_nodes")
            if isinstance(nodes, list):
                raw = len(nodes)
            else:
                raw = 0
        try:
            count = max(0, int(raw))
        except (TypeError, ValueError):
            count = 0
        match_counts.append(count)

    poems_total = len(match_counts)
    poems_with_match = sum(1 for item in match_counts if item > 0)
    total_matches = sum(match_counts)
    return {
        "poems_total": poems_total,
        "poems_with_match": poems_with_match,
        "poems_without_match": max(0, poems_total - poems_with_match),
        "match_coverage_percent": round((poems_with_match * 100.0) / poems_total, 2) if poems_total else 0.0,
        "total_matches": total_matches,
        "avg_match_count": round(total_matches / poems_total, 2) if poems_total else 0.0,
        "min_match_count": min(match_counts) if match_counts else 0,
        "max_match_count": max(match_counts) if match_counts else 0,
        "multi_match_poems": sum(1 for item in match_counts if item >= 2),
    }


def _workspace_dir_from_run_dir(run_dir: Path) -> Path:
    # run_dir is expected as <runtime_workspaces>/<workspace>/runs/<run_id>
    if run_dir.parent.name == "runs":
        return run_dir.parent.parent
    return run_dir.parent


def _runtime_artifact_stats(run_dir: Path) -> dict[str, Any]:
    workspace = _workspace_dir_from_run_dir(run_dir)
    run_meta_raw = _read_json_if_exists(run_dir / "run_meta.json")
    pipeline_request_raw = _read_json_if_exists(workspace / "pipeline_request.json")
    mounting_seed = _read_json_if_exists(run_dir / "poem_mounting_seed.json")
    mounting_full = _read_json_if_exists(run_dir / "poem_mounting_full.json")
    run_meta = _sanitize_legacy_paths(run_meta_raw) if isinstance(run_meta_raw, dict) else {}
    pipeline_request = (
        _sanitize_legacy_paths(pipeline_request_raw) if isinstance(pipeline_request_raw, dict) else {}
    )
    run_meta["run_dir"] = str(run_dir)
    if "source_folder" in run_meta:
        run_meta["source_folder"] = _sanitize_legacy_path_text(str(run_meta["source_folder"]))
    if "source_folder" in pipeline_request:
        pipeline_request["source_folder"] = _sanitize_legacy_path_text(str(pipeline_request["source_folder"]))

    return {
        "run_dir": str(run_dir),
        "workspace": str(workspace),
        "run_meta": run_meta,
        "pipeline_request": pipeline_request,
        "mounting_seed": _mounting_summary(mounting_seed),
        "mounting_full": _mounting_summary(mounting_full),
    }


def build_run_audit(conn, run_id: str, run_dir: Path | None, default_source_folder: Path) -> dict[str, Any]:
    row = conn.execute(
        "SELECT run_id, created_at, model_used, iterations, sample_size, config_json FROM runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"run_id not found: {run_id}")

    config_json = {}
    if row["config_json"]:
        try:
            config_json = json.loads(row["config_json"])
        except json.JSONDecodeError:
            config_json = {}

    source_folder_raw = str(config_json.get("source_folder", "")).strip()
    source_folder = Path(source_folder_raw).expanduser() if source_folder_raw else default_source_folder
    corpus_markdown_files = count_markdown_files(source_folder)

    node_count = int(
        conn.execute("SELECT COUNT(*) FROM nodes WHERE run_id = ?", (run_id,)).fetchone()[0]
    )
    citation_count = int(
        conn.execute("SELECT COUNT(*) FROM citations WHERE run_id = ?", (run_id,)).fetchone()[0]
    )
    citation_with_quote = int(
        conn.execute(
            "SELECT COUNT(*) FROM citations WHERE run_id = ? AND COALESCE(quote, '') <> ''",
            (run_id,),
        ).fetchone()[0]
    )
    distinct_cited_sources = int(
        conn.execute(
            "SELECT COUNT(DISTINCT source_id) FROM citations WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
    )
    source_rows = int(
        conn.execute("SELECT COUNT(*) FROM sources WHERE run_id = ?", (run_id,)).fetchone()[0]
    )
    sources_with_text = int(
        conn.execute(
            "SELECT COUNT(*) FROM sources WHERE run_id = ? AND COALESCE(text, '') <> ''",
            (run_id,),
        ).fetchone()[0]
    )

    db_stats = {
        "nodes": node_count,
        "citations": citation_count,
        "citations_with_quote": citation_with_quote,
        "citations_without_quote": max(0, citation_count - citation_with_quote),
        "distinct_cited_sources": distinct_cited_sources,
        "sources_rows": source_rows,
        "sources_with_text": sources_with_text,
        "sources_without_text": max(0, source_rows - sources_with_text),
        "cited_source_coverage_percent_of_corpus": (
            round((distinct_cited_sources * 100.0) / corpus_markdown_files, 2)
            if corpus_markdown_files
            else 0.0
        ),
    }

    runtime_stats = _runtime_artifact_stats(run_dir) if isinstance(run_dir, Path) else {}

    return {
        "run_id": run_id,
        "run": {
            "created_at": row["created_at"],
            "model_used": row["model_used"],
            "iterations": row["iterations"],
            "sample_size": row["sample_size"],
        },
        "config": config_json,
        "source_folder": str(source_folder),
        "corpus_markdown_files": corpus_markdown_files,
        "db_stats": db_stats,
        "runtime_artifacts": runtime_stats,
    }
