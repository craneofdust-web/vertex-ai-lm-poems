from __future__ import annotations

import html
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


CRAFT_KEYWORDS = (
    "metaphor",
    "imagery",
    "syntax",
    "rhythm",
    "meter",
    "tone",
    "修辞",
    "節奏",
    "意象",
    "語法",
    "技法",
    "格律",
)

THEME_KEYWORDS = (
    "myth",
    "narrative",
    "theme",
    "world",
    "philosophy",
    "symbol",
    "神話",
    "敘事",
    "主題",
    "哲學",
    "象徵",
    "情感",
)


def read_text_with_fallback(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp950"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def read_json(path: Path) -> Any:
    return json.loads(read_text_with_fallback(path))


def infer_lane(name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    craft_score = sum(text.count(keyword.lower()) for keyword in CRAFT_KEYWORDS)
    theme_score = sum(text.count(keyword.lower()) for keyword in THEME_KEYWORDS)
    if craft_score >= theme_score + 1:
        return "craft"
    if theme_score >= craft_score + 1:
        return "theme"
    return "hybrid"


def compute_depths(prereq_map: Dict[str, List[str]]) -> Dict[str, int]:
    memo: Dict[str, int] = {}

    def dfs(node_id: str, stack: set[str]) -> int:
        if node_id in memo:
            return memo[node_id]
        if node_id in stack:
            return 0
        prereq = prereq_map.get(node_id, [])
        if not prereq:
            memo[node_id] = 0
            return 0
        next_stack = set(stack)
        next_stack.add(node_id)
        depth = 1 + max(dfs(parent_id, next_stack) for parent_id in prereq)
        memo[node_id] = depth
        return depth

    for node_id in prereq_map:
        dfs(node_id, set())
    return memo


def compute_stages(
    nodes: List[Dict[str, Any]],
    depth_map: Dict[str, int],
    max_per_stage: int = 8,
) -> Dict[str, int]:
    stages: Dict[str, int] = {node["id"]: int(depth_map.get(node["id"], 0)) for node in nodes}
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for node in nodes:
        depth = int(stages[node["id"]])
        grouped.setdefault(depth, []).append(node)

    for depth in sorted(grouped):
        group = grouped[depth]
        group.sort(
            key=lambda node: (
                -int(node.get("support_count", 0)),
                str(node.get("id", "")),
            )
        )
        for idx, node in enumerate(group):
            stages[node["id"]] = max(stages[node["id"]], depth + idx // max(2, max_per_stage))

    changed = True
    while changed:
        changed = False
        for node in nodes:
            target_id = node["id"]
            required_stage = stages[target_id]
            for source_id in node.get("prerequisites", []):
                required_stage = max(required_stage, int(stages.get(source_id, 0)) + 1)
            if required_stage != stages[target_id]:
                stages[target_id] = required_stage
                changed = True
    return stages


def strip_frontmatter(text: str) -> str:
    content = text.replace("\r\n", "\n").strip()
    if not content.startswith("---\n"):
        return content
    closing = content.find("\n---\n", 4)
    if closing == -1:
        return content
    return content[closing + 5 :].strip()


def source_text_by_id(source_folder: Path, source_id: str) -> str:
    candidates: list[Path] = []
    raw = source_id
    decoded = html.unescape(source_id)

    for sid in (raw, decoded):
        candidates.append(source_folder.joinpath(*sid.split("/")))
        candidates.append(source_folder / sid)

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            return strip_frontmatter(read_text_with_fallback(candidate))
        except OSError:
            continue
    return ""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def count_markdown_files(source_folder: Path) -> int:
    if not source_folder.exists() or not source_folder.is_dir():
        return 0
    try:
        return sum(1 for _ in source_folder.rglob("*.md"))
    except OSError:
        return 0


def _fragment_files(run_dir: Path) -> List[Path]:
    ordered_candidates: List[Path] = []

    # Preferred source: run snapshot
    snapshot_dir = run_dir / "snapshot"
    if snapshot_dir.exists():
        ordered_candidates.extend(sorted(snapshot_dir.glob("skill_web_fragment_*.json")))

    # Fallback source: workspace root used during brainstorming
    # run_dir = <workspace>/runs/<run_id>
    workspace_dir = run_dir.parent.parent if run_dir.parent.name == "runs" else run_dir.parent
    if workspace_dir.exists():
        ordered_candidates.extend(sorted(workspace_dir.glob("skill_web_fragment_*.json")))

    # Additional fallback: run dir root
    ordered_candidates.extend(sorted(run_dir.glob("skill_web_fragment_*.json")))

    deduped: List[Path] = []
    seen_names: set[str] = set()
    for path in ordered_candidates:
        if path.name in seen_names:
            continue
        seen_names.add(path.name)
        deduped.append(path)
    return deduped


def _extract_fragment_index(path: Path) -> int:
    match = re.search(r"skill_web_fragment_(\d+)\.json$", path.name)
    if not match:
        return -1
    return int(match.group(1))


def _mount_match_count(row: Any) -> int:
    if not isinstance(row, dict):
        return 0
    raw = row.get("match_count")
    if raw is None:
        matched_nodes = row.get("matched_nodes")
        if isinstance(matched_nodes, list):
            raw = len(matched_nodes)
        else:
            raw = 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def _mounting_stats(path: Path) -> Dict[str, Any]:
    if not path.is_file():
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
    rows = read_json(path)
    if not isinstance(rows, list):
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
    counts = [_mount_match_count(row) for row in rows]
    poems_total = len(counts)
    poems_with_match = sum(1 for item in counts if item > 0)
    total_matches = sum(counts)
    return {
        "poems_total": poems_total,
        "poems_with_match": poems_with_match,
        "poems_without_match": max(0, poems_total - poems_with_match),
        "match_coverage_percent": round((poems_with_match * 100.0) / poems_total, 2) if poems_total else 0.0,
        "total_matches": total_matches,
        "avg_match_count": round(total_matches / poems_total, 2) if poems_total else 0.0,
        "min_match_count": min(counts) if counts else 0,
        "max_match_count": max(counts) if counts else 0,
        "multi_match_poems": sum(1 for item in counts if item >= 2),
    }


def _mounting_artifact_stats(run_dir: Path) -> Dict[str, Any]:
    full = _mounting_stats(run_dir / "poem_mounting_full.json")
    seed = _mounting_stats(run_dir / "poem_mounting_seed.json")
    return {
        "mounting_full_poems_total": full["poems_total"],
        "mounting_full_poems_with_match": full["poems_with_match"],
        "mounting_full_poems_without_match": full["poems_without_match"],
        "mounting_full_match_coverage_percent": full["match_coverage_percent"],
        "mounting_full_total_matches": full["total_matches"],
        "mounting_full_avg_match_count": full["avg_match_count"],
        "mounting_seed_poems_total": seed["poems_total"],
        "mounting_seed_poems_with_match": seed["poems_with_match"],
        "mounting_seed_poems_without_match": seed["poems_without_match"],
        "mounting_seed_match_coverage_percent": seed["match_coverage_percent"],
        "mounting_seed_total_matches": seed["total_matches"],
        "mounting_seed_avg_match_count": seed["avg_match_count"],
    }


def ingest_run_artifacts(
    conn,
    run_id: str,
    run_dir: Path,
    source_folder: Path,
    model_used: str,
    iterations: int | None,
    sample_size: int | None,
    max_stage_jump: int,
    config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    master_path = run_dir / "master_skill_web.json"
    if not master_path.exists():
        raise FileNotFoundError(f"missing master file: {master_path}")

    master_nodes = read_json(master_path)
    if not isinstance(master_nodes, list):
        raise ValueError("master_skill_web.json must be a JSON array")

    node_ids = {str(node.get("node_id", "")).strip() for node in master_nodes}
    node_ids.discard("")

    prepared_nodes: List[Dict[str, Any]] = []
    citations_by_node: Dict[str, List[Dict[str, Any]]] = {}

    for raw in master_nodes:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("node_id", "")).strip()
        if not node_id:
            continue
        prereq_raw = raw.get("prerequisite_nodes", [])
        prereq = []
        if isinstance(prereq_raw, list):
            for item in prereq_raw:
                source_id = str(item).strip()
                if source_id and source_id in node_ids and source_id != node_id and source_id not in prereq:
                    prereq.append(source_id)
        metadata = raw.get("metadata", {})
        support_count = 0
        if isinstance(metadata, dict):
            support_count = int(metadata.get("support_count", 0) or 0)
        prepared_nodes.append(
            {
                "id": node_id,
                "name": str(raw.get("node_name", "")).strip() or node_id,
                "tier": str(raw.get("node_tier", "")).strip(),
                "description": str(raw.get("description", "")).strip(),
                "unlock_condition": str(raw.get("unlock_condition", "")).strip(),
                "support_count": support_count,
                "prerequisites": prereq,
            }
        )
        raw_citations = raw.get("citations", [])
        citations_by_node[node_id] = raw_citations if isinstance(raw_citations, list) else []

    prereq_map = {node["id"]: list(node["prerequisites"]) for node in prepared_nodes}
    depth_map = compute_depths(prereq_map)
    stage_map = compute_stages(prepared_nodes, depth_map)
    support_by_id = {node["id"]: int(node["support_count"]) for node in prepared_nodes}

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    config_payload = dict(config or {})
    config_payload["max_stage_jump"] = max_stage_jump
    config_payload["run_dir"] = str(run_dir)

    conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
    conn.execute(
        """
        INSERT INTO runs (run_id, created_at, model_used, iterations, sample_size, config_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            created_at,
            model_used,
            iterations,
            sample_size,
            json.dumps(config_payload, ensure_ascii=False),
        ),
    )

    for node in prepared_nodes:
        node_id = node["id"]
        conn.execute(
            """
            INSERT INTO nodes (
                id, name, tier, stage, lane, description, unlock_condition, support_count, run_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                node["name"],
                node["tier"],
                int(stage_map.get(node_id, 0)),
                infer_lane(node["name"], node["description"]),
                node["description"],
                node["unlock_condition"],
                int(node["support_count"]),
                run_id,
            ),
        )

    far_jump_edges = 0
    total_edges = 0
    primary_edges = 0
    for node in prepared_nodes:
        target_id = node["id"]
        target_stage = int(stage_map.get(target_id, 0))
        sorted_prereq = sorted(
            list(node["prerequisites"]),
            key=lambda source_id: (
                -int(depth_map.get(source_id, 0)),
                -int(support_by_id.get(source_id, 0)),
                source_id,
            ),
        )
        if not sorted_prereq:
            continue

        jumps = [max(0, target_stage - int(stage_map.get(source_id, 0))) for source_id in sorted_prereq]
        primary_idx = 0
        for idx, jump in enumerate(jumps):
            if jump <= max_stage_jump:
                primary_idx = idx
                break

        for idx, source_id in enumerate(sorted_prereq):
            stage_jump = jumps[idx]
            edge_type = "primary" if idx == primary_idx else "weak"
            is_direct = 1 if stage_jump <= max_stage_jump else 0
            if is_direct == 0:
                far_jump_edges += 1
            if edge_type == "primary":
                primary_edges += 1
            total_edges += 1
            conn.execute(
                """
                INSERT INTO edges (
                    run_id, source_id, target_id, edge_type, is_direct, stage_jump
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, source_id, target_id, edge_type, is_direct, stage_jump),
            )

    source_records: Dict[str, Dict[str, str]] = {}
    citation_rows = 0
    for node in prepared_nodes:
        node_id = node["id"]
        for citation in citations_by_node.get(node_id, []):
            if not isinstance(citation, dict):
                continue
            source_id = str(citation.get("source_id", "")).strip()
            if not source_id:
                continue
            source_title = str(citation.get("source_title", "")).strip()
            folder_status = str(citation.get("folder_status", "")).strip()
            quote = str(citation.get("quote", "")).strip()
            why = str(citation.get("why", "")).strip()
            conn.execute(
                """
                INSERT INTO citations (
                    run_id, node_id, source_id, source_title, quote, why, folder_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, node_id, source_id, source_title, quote, why, folder_status),
            )
            citation_rows += 1

            if source_id not in source_records:
                source_records[source_id] = {
                    "title": source_title,
                    "folder_status": folder_status,
                }

    sources_with_text = 0
    for source_id, meta in source_records.items():
        text = source_text_by_id(source_folder, source_id)
        if text:
            sources_with_text += 1
        conn.execute(
            """
            INSERT INTO sources (
                source_id, title, folder_status, text, text_hash, run_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                meta.get("title", ""),
                meta.get("folder_status", ""),
                text,
                sha256_text(text) if text else "",
                run_id,
            ),
        )

    fragment_rows = 0
    for fragment_path in _fragment_files(run_dir):
        fragment_index = _extract_fragment_index(fragment_path)
        raw_json = read_text_with_fallback(fragment_path)
        validation_report = ""
        conn.execute(
            """
            INSERT INTO fragments (
                run_id, fragment_index, raw_json, validation_report
            )
            VALUES (?, ?, ?, ?)
            """,
            (run_id, fragment_index, raw_json, validation_report),
        )
        fragment_rows += 1

    corpus_markdown_files = count_markdown_files(source_folder)
    source_coverage_percent = (
        round((len(source_records) * 100.0) / corpus_markdown_files, 2)
        if corpus_markdown_files > 0
        else 0.0
    )
    mounting_stats = _mounting_artifact_stats(run_dir)

    summary = {
        "run_id": run_id,
        "nodes": len(prepared_nodes),
        "edges": total_edges,
        "primary_edges": primary_edges,
        "far_jump_edges": far_jump_edges,
        "citations": citation_rows,
        "sources": len(source_records),
        "sources_with_text": sources_with_text,
        "sources_without_text": max(0, len(source_records) - sources_with_text),
        "corpus_markdown_files": corpus_markdown_files,
        "source_coverage_percent": source_coverage_percent,
        "fragments": fragment_rows,
        "max_stage_jump": max_stage_jump,
        **mounting_stats,
    }

    config_payload["ingest_stats"] = summary
    conn.execute(
        "UPDATE runs SET config_json = ? WHERE run_id = ?",
        (json.dumps(config_payload, ensure_ascii=False), run_id),
    )
    return summary
