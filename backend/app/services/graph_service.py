from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..ingest import source_text_by_id
from ..lineage import build_adjacency, walk_ancestors, walk_descendants


def node_summary(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "tier": row["tier"],
        "stage": int(row["stage"]),
        "lane": row["lane"],
        "support_count": int(row["support_count"]),
    }


def build_graph_payload(
    conn,
    resolved_run_id: str,
    include_weak: bool,
    active_pipeline_version: str,
) -> dict[str, Any]:
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
        "nodes": [node_summary(row) for row in node_rows],
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
            "pipeline_version": active_pipeline_version,
        },
    }


def resolve_source_folder_for_run(conn, default_source_folder: Path, resolved_run_id: str) -> Path:
    source_folder = default_source_folder
    run_config_row = conn.execute(
        "SELECT config_json FROM runs WHERE run_id = ?",
        (resolved_run_id,),
    ).fetchone()
    if run_config_row and run_config_row["config_json"]:
        try:
            config_json = json.loads(run_config_row["config_json"])
        except json.JSONDecodeError:
            config_json = {}
        configured_source = str(config_json.get("source_folder", "")).strip()
        if configured_source:
            candidate = Path(configured_source).expanduser()
            if candidate.exists():
                source_folder = candidate
    return source_folder


def build_node_payload(
    conn,
    resolved_run_id: str,
    node_id: str,
    source_folder: Path,
) -> dict[str, Any]:
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
        SELECT
            c.source_id AS source_id,
            COALESCE(NULLIF(c.source_title, ''), NULLIF(s.title, ''), c.source_id) AS source_title,
            c.quote AS quote,
            c.why AS why,
            c.folder_status AS folder_status,
            COALESCE(s.text, '') AS source_text
        FROM citations c
        LEFT JOIN sources s
          ON s.run_id = c.run_id AND s.source_id = c.source_id
        WHERE c.run_id = ? AND c.node_id = ?
        ORDER BY c.id ASC
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

    source_text_cache: dict[str, str] = {}
    citation_payload = []
    for row in citations:
        source_id = str(row["source_id"])
        source_text = str(row["source_text"] or "").strip()
        if not source_text:
            if source_id not in source_text_cache:
                source_text_cache[source_id] = source_text_by_id(source_folder, source_id)
            source_text = source_text_cache[source_id]
        citation_payload.append(
            {
                "source_id": source_id,
                "source_title": row["source_title"],
                "quote": row["quote"],
                "why": row["why"],
                "folder_status": row["folder_status"],
                "source_text": source_text,
            }
        )

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
        "immediate_downstream": [node_summary(row) for row in downstream],
        "citations": citation_payload,
    }


def build_lineage_payload(conn, resolved_run_id: str, node_id: str) -> dict[str, Any]:
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

    upstream = [node_summary(node_by_id[item]) for item in sorted(ancestor_ids) if item in node_by_id]
    upstream.sort(key=lambda item: (item["stage"], -item["support_count"], item["id"]))

    stage = int(node_row["stage"])
    midstream = [node_summary(row) for row in all_nodes if int(row["stage"]) == stage]
    midstream.sort(key=lambda item: (-item["support_count"], item["id"]))

    downstream = [
        node_summary(node_by_id[item]) for item in sorted(descendant_ids) if item in node_by_id
    ]
    downstream.sort(key=lambda item: (item["stage"], -item["support_count"], item["id"]))

    return {
        "run_id": resolved_run_id,
        "node": node_summary(node_row),
        "lineage": {
            "upstream": upstream,
            "midstream": midstream,
            "downstream": downstream,
        },
    }


def build_search_payload(conn, resolved_run_id: str, query: str, limit: int = 20) -> dict[str, Any]:
    pattern = f"%{query}%"
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
        "query": query,
        "nodes": [node_summary(row) for row in node_rows],
        "sources": [
            {"source_id": row["source_id"], "title": row["title"]} for row in source_rows
        ],
    }
