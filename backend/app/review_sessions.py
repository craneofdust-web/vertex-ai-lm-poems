from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .ingest import read_text_with_fallback, source_text_by_id, strip_frontmatter
from .services import run_service
from .review_sources import resolve_review_source


DEFAULT_WAVE_IDS = (
    "craft_pass",
    "theme_pass",
    "counter_reading_pass",
    "revision_synthesis_pass",
)
REVIEWER_MODE = "single-provider multi-rubric fallback"
PROVIDER_NAME = "codex-local"
MODEL_NAME = "deterministic-rubric-v1"
POLICY_VERSION = "literary-salon-v0.1"
DATE_KEYS = (
    "date",
    "created",
    "created_at",
    "建立時間",
    "創作時間",
    "時間",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_if_exists(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return _read_json(path)
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def _workspace_dir_from_run_dir(run_dir: Path) -> Path:
    if run_dir.parent.name == "runs":
        return run_dir.parent.parent
    return run_dir.parent


def _session_dir(run_dir: Path, session_id: str) -> Path:
    return _workspace_dir_from_run_dir(run_dir) / "literary_salon" / session_id


def _mounting_path(run_dir: Path) -> Path:
    return run_dir / "poem_mounting_full.json"


def _batch_file_name(index: int) -> str:
    return f"batch_{index:03d}.jsonl"


def _session_paths(session_dir: Path) -> dict[str, Path]:
    return {
        "root": session_dir,
        "targets": session_dir / "review_targets.jsonl",
        "batches": session_dir / "review_batches",
        "batch_index": session_dir / "review_batches" / "index.json",
        "waves": session_dir / "review_waves",
        "run_meta": session_dir / "run_meta.json",
        "session_status_json": session_dir / "session_status.json",
        "session_status_md": session_dir / "session_status.md",
        "consensus_json": session_dir / "consensus_report.json",
        "consensus_md": session_dir / "consensus_report.md",
    }


def _parse_frontmatter(raw_text: str) -> dict[str, Any]:
    text = raw_text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}
    closing = text.find("\n---\n", 4)
    if closing < 0:
        return {}
    payload = text[4:closing]
    result: dict[str, Any] = {}
    current_key = ""
    for raw_line in payload.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        match = re.match(r"^([A-Za-z0-9_\-\u4e00-\u9fff]+)\s*:\s*(.*)$", line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            if value:
                result[key] = value
                current_key = ""
            else:
                result[key] = []
                current_key = key
            continue
        if current_key and line.lstrip().startswith("- "):
            item = line.lstrip()[2:].strip()
            current = result.get(current_key)
            if isinstance(current, list):
                current.append(item)
    return result


def _first_frontmatter_value(frontmatter: dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = frontmatter.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            if value:
                return str(value[0]).strip()
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _normalize_completion_status(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    match = re.search(r"([0-5])", value)
    if match:
        return match.group(1)
    return value


def _infer_creation_time_hint(source_id: str, source_path: Path | None, frontmatter: dict[str, Any]) -> dict[str, str]:
    explicit = _first_frontmatter_value(frontmatter, DATE_KEYS)
    if explicit:
        return {"value": explicit, "source": "frontmatter", "confidence": "high"}
    filename = Path(source_id).name
    match = re.search(r"(\d{4}-\d{2}-\d{2})(?:[T_].*)?", filename)
    if match:
        return {"value": match.group(1), "source": "filename", "confidence": "medium"}
    if source_path and source_path.exists():
        return {"value": "filesystem_only", "source": "filesystem", "confidence": "low"}
    return {"value": "unknown", "source": "missing", "confidence": "low"}


def _infer_maturity_bucket(folder_status: str, completion_status: str) -> str:
    folder = str(folder_status or "")
    if any(token in folder for token in ("未完成", "創作中", "草稿")):
        return "in_progress"
    if any(token in folder for token in ("未整理作品", "1 文學記錄")):
        return "early_archive"
    if completion_status in {"0", "1", "2"}:
        return "in_progress"
    if completion_status == "3":
        return "maturing"
    if completion_status in {"4", "5"}:
        return "mature"
    if any(token in folder for token in ("未分類的完整詩", "1 純粹文學", "原道")):
        return "mature"
    return "unknown"


def _comparison_policy_for_bucket(bucket: str) -> str:
    if bucket in {"early_archive", "in_progress"}:
        return "compare_with_same_stage_only"
    if bucket in {"maturing", "unknown"}:
        return "compare_with_caution"
    return "can_enter_general_pool"


def _review_mode_for_bucket(bucket: str) -> str:
    if bucket == "mature":
        return "finished_work_mode"
    if bucket == "in_progress":
        return "in_progress_mode"
    if bucket == "early_archive":
        return "early_archive_mode"
    return "experimental_transition_mode"


def _metadata_confidence(completion_status: str, creation_hint: dict[str, str]) -> dict[str, str]:
    return {
        "folder_status": "high",
        "completion_status": "high" if completion_status else "low",
        "creation_time_hint": creation_hint.get("confidence", "low"),
    }


def _compute_text_metrics(full_text: str) -> dict[str, Any]:
    body = strip_frontmatter(full_text)
    raw_lines = body.splitlines()
    non_empty_lines = [line.strip() for line in raw_lines if line.strip()]
    unique_lines = set(non_empty_lines)
    repeated_lines = max(0, len(non_empty_lines) - len(unique_lines))
    char_count = len(body.replace("\n", ""))
    avg_line_length = round(char_count / len(non_empty_lines), 2) if non_empty_lines else 0.0
    return {
        "line_count": len(non_empty_lines),
        "char_count": char_count,
        "avg_line_length": avg_line_length,
        "repeated_line_count": repeated_lines,
        "has_workbench_marks": bool(re.search(r"[（(].+[)）]|\*", body)),
        "has_window_signal": bool(re.search(r"窗|window", body, flags=re.IGNORECASE)),
        "has_turn_signal": bool(re.search(r"但|卻|然而|可是|but|yet|however", body, flags=re.IGNORECASE)),
        "has_civic_scale_signal": bool(re.search(r"城|國|帝|文明|制度|市場|city|market|institution", body, flags=re.IGNORECASE)),
    }


def _top_nodes(matches: list[dict[str, Any]], limit: int = 3) -> list[str]:
    out: list[str] = []
    for item in matches[:limit]:
        name = str(item.get("node_name") or item.get("node_id") or "").strip()
        if name:
            out.append(name)
    return out


def _source_path(source_folder: Path, source_id: str) -> Path:
    return source_folder.joinpath(*source_id.split("/"))


def _load_db_source_rows(conn, run_id: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT source_id, title, folder_status, text FROM sources WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    return {
        str(row["source_id"]): {
            "title": str(row["title"] or "").strip(),
            "folder_status": str(row["folder_status"] or "").strip(),
            "text": str(row["text"] or ""),
        }
        for row in rows
    }


def _load_run_config(conn, run_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT config_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not row or not row["config_json"]:
        return {}
    try:
        payload = json.loads(row["config_json"])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_source_folder(conn, settings, run_id: str, source_folder: Path | None) -> Path:
    if source_folder and source_folder.exists() and source_folder.is_dir():
        return source_folder
    config = _load_run_config(conn, run_id)
    configured = str(config.get("source_folder", "")).strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.exists() and candidate.is_dir():
            return candidate
    return settings.source_folder


def _load_run_meta(run_dir: Path) -> dict[str, Any]:
    return _read_json_if_exists(run_dir / "run_meta.json") or {}


def _review_excerpt(full_text: str, limit: int = 420) -> str:
    body = strip_frontmatter(full_text).strip()
    if len(body) <= limit:
        return body
    return body[:limit].rstrip() + "..."


def _build_target(
    source_row: dict[str, Any],
    source_folder: Path,
    db_sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_id = str(source_row.get("source_id") or "").strip()
    if not source_id:
        raise ValueError("missing source_id in mounting row")
    source_path = _source_path(source_folder, source_id)
    raw_text = ""
    if source_path.exists() and source_path.is_file():
        raw_text = read_text_with_fallback(source_path)
    if not raw_text:
        raw_text = str(db_sources.get(source_id, {}).get("text") or "")
    frontmatter = _parse_frontmatter(raw_text)
    completion_status = _normalize_completion_status(_first_frontmatter_value(frontmatter, ("完成度", "completion")))
    creation_hint = _infer_creation_time_hint(source_id, source_path if source_path.exists() else None, frontmatter)
    folder_status = (
        str(source_row.get("folder_status") or "").strip()
        or str(db_sources.get(source_id, {}).get("folder_status") or "").strip()
        or source_id.split("/", 1)[0]
    )
    maturity_bucket = _infer_maturity_bucket(folder_status, completion_status)
    comparison_policy = _comparison_policy_for_bucket(maturity_bucket)
    review_mode = _review_mode_for_bucket(maturity_bucket)
    matches = source_row.get("matched_nodes")
    matched_nodes = matches if isinstance(matches, list) else []
    metrics = _compute_text_metrics(raw_text)
    title = (
        str(source_row.get("source_title") or "").strip()
        or str(db_sources.get(source_id, {}).get("title") or "").strip()
        or Path(source_id).name
    )
    return {
        "target_id": source_id,
        "source_id": source_id,
        "title": title,
        "folder_status": folder_status,
        "completion_status": completion_status or "unknown",
        "creation_time_hint": creation_hint.get("value", "unknown"),
        "creation_time_hint_source": creation_hint.get("source", "missing"),
        "creation_time_hint_confidence": creation_hint.get("confidence", "low"),
        "maturity_bucket": maturity_bucket,
        "comparison_policy": comparison_policy,
        "review_mode": review_mode,
        "metadata_confidence": _metadata_confidence(completion_status, creation_hint),
        "text_available": bool(raw_text.strip()),
        "full_text": strip_frontmatter(raw_text).strip(),
        "review_excerpt": _review_excerpt(raw_text),
        "matched_nodes": matched_nodes,
        "match_count": int(source_row.get("match_count") or len(matched_nodes) or 0),
        "text_metrics": metrics,
        "author_context_flags": {
            "window_strategy_signal": bool(metrics["has_window_signal"]),
            "construction_zone_signal": bool(metrics["has_workbench_marks"]),
            "self_undermining_signal": bool(metrics["has_turn_signal"]),
            "civic_scale_signal": bool(metrics["has_civic_scale_signal"]),
        },
    }


def export_review_targets(
    conn,
    settings,
    run_id: str,
    session_id: str,
    source_folder: Path | None = None,
    batch_size: int = 50,
    limit: int | None = None,
    wave_ids: Iterable[str] = DEFAULT_WAVE_IDS,
) -> dict[str, Any]:
    run_dir = run_service.runtime_run_dir_by_id(settings, run_id)
    if not isinstance(run_dir, Path):
        raise ValueError(f"run_id not found in runtime_workspaces: {run_id}")
    mounting_rows = _read_json(_mounting_path(run_dir))
    if not isinstance(mounting_rows, list):
        raise ValueError("poem_mounting_full.json must be a JSON array")

    resolved_source_folder = _resolve_source_folder(conn, settings, run_id, source_folder)
    db_sources = _load_db_source_rows(conn, run_id)
    run_meta = _load_run_meta(run_dir)
    config = _load_run_config(conn, run_id)
    session_dir = _session_dir(run_dir, session_id)
    paths = _session_paths(session_dir)
    paths["root"].mkdir(parents=True, exist_ok=True)

    ordered_rows = sorted(
        mounting_rows,
        key=lambda item: (
            str(item.get("folder_status") or ""),
            str(item.get("source_id") or ""),
        ),
    )
    if limit is not None and limit > 0:
        ordered_rows = ordered_rows[:limit]

    targets = [_build_target(item, resolved_source_folder, db_sources) for item in ordered_rows]
    _write_jsonl(paths["targets"], targets)

    capped_batch_size = max(1, int(batch_size))
    batches: list[dict[str, Any]] = []
    for index in range(0, len(targets), capped_batch_size):
        batch_number = index // capped_batch_size + 1
        batch_items = targets[index : index + capped_batch_size]
        batch_name = _batch_file_name(batch_number)
        batch_path = paths["batches"] / batch_name
        _write_jsonl(batch_path, batch_items)
        batches.append(
            {
                "batch_id": batch_name.removesuffix(".jsonl"),
                "file": str(batch_path),
                "target_count": len(batch_items),
                "first_target_id": batch_items[0]["target_id"] if batch_items else "",
                "last_target_id": batch_items[-1]["target_id"] if batch_items else "",
            }
        )

    creation_confidence = Counter(target["creation_time_hint_confidence"] for target in targets)
    completion_available = sum(1 for target in targets if target["completion_status"] != "unknown")
    run_meta_payload = {
        "session_id": session_id,
        "run_id": run_id,
        "created_at": utc_now(),
        "reviewer_mode": REVIEWER_MODE,
        "provider": PROVIDER_NAME,
        "model": MODEL_NAME,
        "policy_version": POLICY_VERSION,
        "wave_ids": list(wave_ids),
        "source_folder": str(resolved_source_folder),
        "source_folder_exists": resolved_source_folder.exists(),
        "batch_size": capped_batch_size,
        "batch_count": len(batches),
        "target_count": len(targets),
        "mounted_poems_total": int(run_meta.get("poems_total", len(targets)) or len(targets)),
        "config_snapshot": {
            "pipeline_version": config.get("pipeline_version", "v0.3.1"),
            "mode": config.get("mode", "full"),
            "project_id": str(config.get("project_id", "")).strip(),
        },
        "metadata_readability": {
            "folder_status": {"available": len(targets), "confidence": "high"},
            "completion_status": {"available": completion_available, "confidence": "partial"},
            "creation_time_hint": {
                "available": sum(1 for target in targets if target["creation_time_hint"] != "unknown"),
                "confidence_counts": dict(creation_confidence),
            },
        },
    }
    _write_json(paths["run_meta"], run_meta_payload)
    _write_json(paths["batch_index"], {"batches": batches})
    status = build_session_status(session_dir)
    return {
        "session_dir": str(session_dir),
        "target_count": len(targets),
        "batch_count": len(batches),
        "status": status,
    }


def _support_examples(targets: list[dict[str, Any]], limit: int = 5) -> list[str]:
    names = [f"{item['title']} ({item['source_id']})" for item in targets[:limit]]
    return names


def _confidence_value(target: dict[str, Any]) -> float:
    value = 0.45
    if target.get("text_available"):
        value += 0.2
    if target.get("completion_status") not in {"", "unknown"}:
        value += 0.1
    if target.get("creation_time_hint_confidence") in {"high", "medium"}:
        value += 0.1
    if int(target.get("match_count", 0) or 0) >= 2:
        value += 0.1
    return round(max(0.25, min(0.92, value)), 2)


def _stage_caution(target: dict[str, Any]) -> str:
    review_mode = target.get("review_mode")
    if review_mode == "in_progress_mode":
        return "Judge the draft by trajectory and experiment, not by final polish."
    if review_mode == "early_archive_mode":
        return "Keep this in its developmental era instead of mixing it with late mature work."
    if target.get("creation_time_hint_confidence") in {"low", "unknown"}:
        return "Chronology confidence is low, so developmental claims should stay cautious."
    return "This target can enter broader comparison, but stage-aware caution still applies."


def _anticipated_note(target: dict[str, Any], top_nodes: list[str]) -> str:
    if top_nodes:
        return f"Potential future continuity appears around {', '.join(top_nodes[:2])}."
    if target.get("author_context_flags", {}).get("window_strategy_signal"):
        return "The recurring window/interface signal may matter more than a linear thesis here."
    return "The next human pass should test what this poem anticipates without forcing one mature template on it."


def _baseline_works(target: dict[str, Any], top_nodes: list[str]) -> list[str]:
    metrics = target["text_metrics"]
    works: list[str] = []
    if metrics["line_count"] >= 8:
        works.append(f"The poem sustains a multi-line field across {metrics['line_count']} active lines.")
    if int(target.get("match_count", 0) or 0) >= 2:
        works.append(f"The current graph already anchors {target['match_count']} concrete entry points.")
    elif int(target.get("match_count", 0) or 0) == 1:
        works.append("At least one line already has a concrete graph anchor.")
    if not works and top_nodes:
        works.append(f"The current mapping still surfaces a readable cluster around {', '.join(top_nodes[:2])}.")
    if not works:
        works.append("There is at least a legible poetic gesture worth preserving for later review.")
    return works[:2]


def _craft_review(target: dict[str, Any], batch_id: str) -> dict[str, Any]:
    metrics = target["text_metrics"]
    top_nodes = _top_nodes(target.get("matched_nodes", []))
    works = _baseline_works(target, top_nodes)
    testing: list[str] = []
    gaps: list[str] = []
    if metrics["has_workbench_marks"]:
        testing.append("Brackets or note marks suggest rhythm-first drafting is still visible on the page.")
    if metrics["avg_line_length"] and metrics["avg_line_length"] <= 12:
        testing.append("Short line pressure is carrying part of the craft energy.")
    if target.get("review_mode") == "in_progress_mode":
        gaps.append("Do not force polish before the central turn and line movement settle.")
    if int(target.get("match_count", 0) or 0) == 0:
        gaps.append("The current graph offers no concrete anchor yet, so craft claims remain provisional.")
    if not gaps and metrics["line_count"] < 6:
        gaps.append("The piece may still be closer to a core fragment than a fully stabilized poem.")
    stance = "support"
    if not target.get("text_available"):
        stance = "reject"
    elif target.get("review_mode") in {"in_progress_mode", "experimental_transition_mode"} or metrics["has_workbench_marks"]:
        stance = "revise"
    return {
        "wave_id": "craft_pass",
        "provider": PROVIDER_NAME,
        "model": MODEL_NAME,
        "policy_version": POLICY_VERSION,
        "reviewer_mode": REVIEWER_MODE,
        "batch_id": batch_id,
        "target_id": target["target_id"],
        "timestamp": utc_now(),
        "review_mode": target["review_mode"],
        "maturity_bucket": target["maturity_bucket"],
        "comparison_policy": target["comparison_policy"],
        "stance": stance,
        "confidence": _confidence_value(target),
        "what_works": works,
        "what_is_being_tested": testing[:2],
        "structural_gaps": gaps[:2],
        "do_not_judge_harshly": [_stage_caution(target)],
        "anticipated_later_work": [_anticipated_note(target, top_nodes)],
        "rationale": " ".join((works + testing + gaps)[:3]),
    }


def _theme_review(target: dict[str, Any], batch_id: str) -> dict[str, Any]:
    top_nodes = _top_nodes(target.get("matched_nodes", []))
    metrics = target["text_metrics"]
    works = _baseline_works(target, top_nodes)
    if top_nodes:
        works.append(f"The current semantic cluster leans toward {', '.join(top_nodes[:2])}.")
    testing: list[str] = []
    if metrics["has_window_signal"]:
        testing.append("A recurring window/interface signal may organize the poem more than a thesis statement does.")
    if metrics["has_civic_scale_signal"]:
        testing.append("There are hints of scale beyond the private scene, which can support a larger thematic frame.")
    gaps: list[str] = []
    if target.get("review_mode") == "early_archive_mode":
        gaps.append("Read the thematic field within its earlier developmental layer, not as late-corpus doctrine.")
    elif int(target.get("match_count", 0) or 0) <= 1:
        gaps.append("Theme claims still need more than one isolated anchor before they harden.")
    stance = "support"
    if not target.get("text_available"):
        stance = "reject"
    elif target.get("comparison_policy") != "can_enter_general_pool":
        stance = "revise"
    return {
        "wave_id": "theme_pass",
        "provider": PROVIDER_NAME,
        "model": MODEL_NAME,
        "policy_version": POLICY_VERSION,
        "reviewer_mode": REVIEWER_MODE,
        "batch_id": batch_id,
        "target_id": target["target_id"],
        "timestamp": utc_now(),
        "review_mode": target["review_mode"],
        "maturity_bucket": target["maturity_bucket"],
        "comparison_policy": target["comparison_policy"],
        "stance": stance,
        "confidence": _confidence_value(target),
        "what_works": works[:2],
        "what_is_being_tested": testing[:2],
        "structural_gaps": gaps[:2],
        "do_not_judge_harshly": [_stage_caution(target)],
        "anticipated_later_work": [_anticipated_note(target, top_nodes)],
        "rationale": " ".join((works + testing + gaps)[:3]),
    }


def _counter_review(target: dict[str, Any], batch_id: str) -> dict[str, Any]:
    top_nodes = _top_nodes(target.get("matched_nodes", []))
    works = [
        "The review stays anchored to quoted evidence instead of rewarding generic solemnity.",
    ]
    if int(target.get("match_count", 0) or 0) >= 2:
        works.append("Multiple existing anchors reduce the risk of a totally free-floating reading.")
    testing: list[str] = []
    if target.get("creation_time_hint_confidence") in {"low", "unknown"}:
        testing.append("Chronology is uncertain, so any developmental claim should be downgraded.")
    if target.get("author_context_flags", {}).get("window_strategy_signal"):
        testing.append("Do not collapse a recurring interface image into a simple inspirational thesis.")
    gaps: list[str] = []
    if target.get("comparison_policy") == "compare_with_same_stage_only":
        gaps.append("This poem should not be flattened into a single contest with mature late work.")
    if int(target.get("match_count", 0) or 0) <= 1:
        gaps.append("The current evidence remains too thin for a strong affirmative claim.")
    stance = "revise"
    if not target.get("text_available"):
        stance = "reject"
    elif target.get("comparison_policy") == "can_enter_general_pool" and int(target.get("match_count", 0) or 0) >= 3:
        stance = "support"
    elif int(target.get("match_count", 0) or 0) <= 1:
        stance = "reject"
    return {
        "wave_id": "counter_reading_pass",
        "provider": PROVIDER_NAME,
        "model": MODEL_NAME,
        "policy_version": POLICY_VERSION,
        "reviewer_mode": REVIEWER_MODE,
        "batch_id": batch_id,
        "target_id": target["target_id"],
        "timestamp": utc_now(),
        "review_mode": target["review_mode"],
        "maturity_bucket": target["maturity_bucket"],
        "comparison_policy": target["comparison_policy"],
        "stance": stance,
        "confidence": _confidence_value(target),
        "what_works": works[:2],
        "what_is_being_tested": testing[:2],
        "structural_gaps": gaps[:2],
        "do_not_judge_harshly": [_stage_caution(target)],
        "anticipated_later_work": [_anticipated_note(target, top_nodes)],
        "rationale": " ".join((works + testing + gaps)[:3]),
    }


def _revision_review(target: dict[str, Any], batch_id: str) -> dict[str, Any]:
    top_nodes = _top_nodes(target.get("matched_nodes", []))
    works = [
        "The current graph mapping is already usable as a human review packet.",
    ]
    if top_nodes:
        works.append(f"A focused next pass can test {', '.join(top_nodes[:2])} without rewriting the whole reading frame.")
    testing: list[str] = [
        "Protect the sound field and structural load-bearing lines before concept cleanup.",
    ]
    gaps: list[str] = []
    if target.get("review_mode") == "in_progress_mode":
        gaps.append("Revision should preserve live experiments instead of sanding them into fake closure.")
    elif target.get("review_mode") == "early_archive_mode":
        gaps.append("Archive work should be curated as developmental evidence, not aggressively normalized.")
    if int(target.get("match_count", 0) or 0) == 0:
        gaps.append("Human re-read is needed before this target can support consensus claims.")
    stance = "support"
    if not target.get("text_available"):
        stance = "reject"
    elif gaps:
        stance = "revise"
    return {
        "wave_id": "revision_synthesis_pass",
        "provider": PROVIDER_NAME,
        "model": MODEL_NAME,
        "policy_version": POLICY_VERSION,
        "reviewer_mode": REVIEWER_MODE,
        "batch_id": batch_id,
        "target_id": target["target_id"],
        "timestamp": utc_now(),
        "review_mode": target["review_mode"],
        "maturity_bucket": target["maturity_bucket"],
        "comparison_policy": target["comparison_policy"],
        "stance": stance,
        "confidence": _confidence_value(target),
        "what_works": works[:2],
        "what_is_being_tested": testing[:2],
        "structural_gaps": gaps[:2],
        "do_not_judge_harshly": [_stage_caution(target)],
        "anticipated_later_work": [_anticipated_note(target, top_nodes)],
        "rationale": " ".join((works + testing + gaps)[:3]),
    }


def _build_review(target: dict[str, Any], wave_id: str, batch_id: str) -> dict[str, Any]:
    builders = {
        "craft_pass": _craft_review,
        "theme_pass": _theme_review,
        "counter_reading_pass": _counter_review,
        "revision_synthesis_pass": _revision_review,
    }
    try:
        builder = builders[wave_id]
    except KeyError as exc:
        raise ValueError(f"unsupported wave_id: {wave_id}") from exc
    review = builder(target, batch_id)
    review["title"] = target["title"]
    review["source_id"] = target["source_id"]
    review["match_count"] = int(target.get("match_count", 0) or 0)
    review["top_nodes"] = _top_nodes(target.get("matched_nodes", []))
    review.update(resolve_review_source(str(review.get("provider") or ""), str(review.get("model") or "")))
    return review


def run_review_wave(
    settings,
    run_id: str,
    session_id: str,
    wave_id: str,
    force: bool = False,
) -> dict[str, Any]:
    run_dir = run_service.runtime_run_dir_by_id(settings, run_id)
    if not isinstance(run_dir, Path):
        raise ValueError(f"run_id not found in runtime_workspaces: {run_id}")
    session_dir = _session_dir(run_dir, session_id)
    paths = _session_paths(session_dir)
    batch_index = _read_json(paths["batch_index"])
    if not isinstance(batch_index, dict):
        raise ValueError("review_batches/index.json missing or invalid")
    batches = batch_index.get("batches")
    if not isinstance(batches, list) or not batches:
        raise ValueError("no review batches available")

    wave_dir = paths["waves"] / wave_id
    wave_dir.mkdir(parents=True, exist_ok=True)
    completed_batches = 0
    total_reviews = 0
    for batch in batches:
        file_path = Path(str(batch.get("file") or "")).expanduser()
        if not file_path.is_file():
            continue
        batch_id = str(batch.get("batch_id") or file_path.stem)
        out_path = wave_dir / file_path.name
        if out_path.exists() and not force:
            total_reviews += len(_load_jsonl(out_path))
            completed_batches += 1
            continue
        targets = _load_jsonl(file_path)
        total_reviews += _write_jsonl(
            out_path,
            (_build_review(target, wave_id, batch_id) for target in targets),
        )
        completed_batches += 1

    summary = {
        "wave_id": wave_id,
        "batch_count": completed_batches,
        "review_count": total_reviews,
        "updated_at": utc_now(),
    }
    _write_json(wave_dir / "wave_summary.json", summary)
    build_session_status(session_dir)
    return summary


def _consensus_status(reviews: list[dict[str, Any]]) -> str:
    stances = Counter(str(item.get("stance") or "revise") for item in reviews)
    if stances.get("reject", 0) >= 2:
        return "reject"
    if stances.get("support", 0) >= 3 and stances.get("reject", 0) == 0:
        return "support"
    return "revise"


def _merge_bullets(reviews: list[dict[str, Any]], key: str, limit: int = 3) -> list[str]:
    seen: list[str] = []
    for review in reviews:
        values = review.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.append(text)
            if len(seen) >= limit:
                return seen
    return seen


def _build_consensus_markdown(report: dict[str, Any]) -> str:
    overview = report["overview"]
    aggregate = report["aggregate"]
    support_by_bucket = report["support_examples_by_bucket"]
    lines = [
        "# Literary Salon Consensus Report",
        "",
        f"- run_id: `{overview['run_id']}`",
        f"- session_id: `{overview['session_id']}`",
        f"- reviewer_mode: `{overview['reviewer_mode']}`",
        f"- target_count: `{overview['target_count']}`",
        f"- full_text_available_count: `{overview['full_text_available_count']}`",
        f"- wave_count: `{overview['wave_count']}`",
        f"- consensus_support: `{aggregate['consensus_counts'].get('support', 0)}`",
        f"- consensus_revise: `{aggregate['consensus_counts'].get('revise', 0)}`",
        f"- consensus_reject: `{aggregate['consensus_counts'].get('reject', 0)}`",
        "",
        "## By Maturity Bucket",
        "",
    ]
    for bucket, count in aggregate["maturity_bucket_counts"].items():
        lines.append(f"- `{bucket}`: `{count}`")
    lines.extend(["", "## Support Examples (bucketed)", ""])
    for bucket, items in support_by_bucket.items():
        lines.append(f"### {bucket}")
        if not items:
            lines.append("- none")
        else:
            for item in items:
                lines.append(f"- {item}")
        lines.append("")
    lines.extend([
        "## Notes",
        "",
        "- This session uses single-provider multi-rubric fallback, not a multi-provider consensus run.",
        "- Stage-aware caution remains active; unfinished and early works are not flattened into one ranking pool.",
        "",
    ])
    return "\n".join(lines).strip() + "\n"


def merge_review_waves(settings, run_id: str, session_id: str) -> dict[str, Any]:
    run_dir = run_service.runtime_run_dir_by_id(settings, run_id)
    if not isinstance(run_dir, Path):
        raise ValueError(f"run_id not found in runtime_workspaces: {run_id}")
    session_dir = _session_dir(run_dir, session_id)
    paths = _session_paths(session_dir)
    run_meta = _read_json(paths["run_meta"])
    targets = {row["target_id"]: row for row in _load_jsonl(paths["targets"])}
    grouped_reviews: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for wave_id in run_meta.get("wave_ids", DEFAULT_WAVE_IDS):
        wave_dir = paths["waves"] / str(wave_id)
        for batch_path in sorted(wave_dir.glob("batch_*.jsonl")):
            for review in _load_jsonl(batch_path):
                grouped_reviews[str(review.get("target_id") or "")].append(review)

    per_target: list[dict[str, Any]] = []
    support_examples_by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    consensus_counts: Counter[str] = Counter()
    maturity_bucket_counts: Counter[str] = Counter()
    for target_id, target in targets.items():
        reviews = grouped_reviews.get(target_id, [])
        consensus = _consensus_status(reviews) if reviews else "revise"
        consensus_counts[consensus] += 1
        bucket = str(target.get("maturity_bucket") or "unknown")
        maturity_bucket_counts[bucket] += 1
        merged = {
            "target_id": target_id,
            "source_id": target["source_id"],
            "title": target["title"],
            "maturity_bucket": bucket,
            "review_mode": target["review_mode"],
            "comparison_policy": target["comparison_policy"],
            "consensus": consensus,
            "stance_counts": dict(Counter(str(item.get("stance") or "revise") for item in reviews)),
            "what_works": _merge_bullets(reviews, "what_works"),
            "what_is_being_tested": _merge_bullets(reviews, "what_is_being_tested"),
            "structural_gaps": _merge_bullets(reviews, "structural_gaps"),
            "do_not_judge_harshly": _merge_bullets(reviews, "do_not_judge_harshly", limit=2),
            "anticipated_later_work": _merge_bullets(reviews, "anticipated_later_work", limit=2),
            "review_count": len(reviews),
            "disagreement": len({str(item.get('stance') or 'revise') for item in reviews}) > 1,
        }
        if consensus == "support":
            support_examples_by_bucket[bucket].append(merged)
        per_target.append(merged)

    report = {
        "overview": {
            "run_id": run_id,
            "session_id": session_id,
            "reviewer_mode": run_meta.get("reviewer_mode", REVIEWER_MODE),
            "target_count": len(targets),
            "full_text_available_count": sum(1 for item in targets.values() if item.get("text_available")),
            "wave_count": len(run_meta.get("wave_ids", DEFAULT_WAVE_IDS)),
            "updated_at": utc_now(),
        },
        "aggregate": {
            "consensus_counts": dict(consensus_counts),
            "maturity_bucket_counts": dict(maturity_bucket_counts),
        },
        "support_examples_by_bucket": {
            bucket: _support_examples(items) for bucket, items in support_examples_by_bucket.items()
        },
        "targets": per_target,
    }
    _write_json(paths["consensus_json"], report)
    paths["consensus_md"].write_text(_build_consensus_markdown(report), encoding="utf-8")
    build_session_status(session_dir)
    return report


def build_session_status(session_dir: Path) -> dict[str, Any]:
    paths = _session_paths(session_dir)
    run_meta = _read_json_if_exists(paths["run_meta"]) or {}
    batch_index = _read_json_if_exists(paths["batch_index"]) or {"batches": []}
    batches = batch_index.get("batches") if isinstance(batch_index, dict) else []
    batch_targets: dict[str, int] = {}
    if isinstance(batches, list):
        for item in batches:
            if not isinstance(item, dict):
                continue
            batch_id = str(item.get("batch_id") or "").strip()
            if not batch_id:
                continue
            try:
                batch_targets[batch_id] = int(item.get("target_count") or 0)
            except (TypeError, ValueError):
                batch_targets[batch_id] = 0
    target_count = 0
    if paths["targets"].is_file():
        target_count = len(_load_jsonl(paths["targets"]))
    wave_status: dict[str, dict[str, Any]] = {}
    expected_batch_count = len(batches) if isinstance(batches, list) else 0
    for wave_id in run_meta.get("wave_ids", DEFAULT_WAVE_IDS):
        wave_dir = paths["waves"] / str(wave_id)
        batch_files = sorted(wave_dir.glob("batch_*.jsonl")) if wave_dir.exists() else []
        review_count = 0
        full_batches = 0
        partial_batches = 0
        missing_targets = 0
        for path in batch_files:
            batch_id = path.stem
            actual_count = len(_load_jsonl(path))
            review_count += actual_count
            expected_count = int(batch_targets.get(batch_id, 0) or 0)
            if expected_count > 0 and actual_count >= expected_count:
                full_batches += 1
            elif actual_count > 0:
                partial_batches += 1
                if expected_count > actual_count:
                    missing_targets += expected_count - actual_count
        wave_status[str(wave_id)] = {
            "completed_batches": full_batches,
            "partial_batches": partial_batches,
            "expected_batches": expected_batch_count,
            "review_count": review_count,
            "missing_targets": missing_targets,
            "complete": expected_batch_count > 0 and full_batches >= expected_batch_count,
        }

    status = {
        "run_id": run_meta.get("run_id", ""),
        "session_id": run_meta.get("session_id", session_dir.name),
        "target_count": target_count,
        "batch_count": expected_batch_count,
        "wave_status": wave_status,
        "consensus_report_ready": paths["consensus_json"].is_file() and paths["consensus_md"].is_file(),
        "updated_at": utc_now(),
    }
    _write_json(paths["session_status_json"], status)
    md_lines = [
        "# Review Session Status",
        "",
        f"- run_id: `{status['run_id']}`",
        f"- session_id: `{status['session_id']}`",
        f"- target_count: `{status['target_count']}`",
        f"- batch_count: `{status['batch_count']}`",
        f"- consensus_report_ready: `{status['consensus_report_ready']}`",
        "",
        "## Waves",
        "",
    ]
    for wave_id, payload in wave_status.items():
        md_lines.append(
            f"- `{wave_id}`: `{payload['completed_batches']}/{payload['expected_batches']}` full batches, `{payload['partial_batches']}` partial, `{payload['review_count']}` reviews, `{payload['missing_targets']}` missing targets"
        )
    paths["session_status_md"].write_text("\n".join(md_lines).strip() + "\n", encoding="utf-8")
    return status


def list_review_sessions(settings, run_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for workspace in settings.runtime_root.iterdir():
        if not workspace.is_dir():
            continue
        if run_id and workspace.name != run_id:
            continue
        salon_root = workspace / "literary_salon"
        if not salon_root.is_dir():
            continue
        for session_dir in sorted(salon_root.iterdir()):
            if not session_dir.is_dir():
                continue
            status = _read_json_if_exists(session_dir / "session_status.json") or {}
            run_meta = _read_json_if_exists(session_dir / "run_meta.json") or {}
            stat_target = session_dir / "session_status.json"
            try:
                mtime = float(stat_target.stat().st_mtime if stat_target.exists() else session_dir.stat().st_mtime)
            except OSError:
                mtime = 0.0
            items.append(
                {
                    "run_id": run_meta.get("run_id", workspace.name),
                    "session_id": run_meta.get("session_id", session_dir.name),
                    "target_count": status.get("target_count", run_meta.get("target_count", 0)),
                    "batch_count": status.get("batch_count", run_meta.get("batch_count", 0)),
                    "consensus_report_ready": bool(status.get("consensus_report_ready")),
                    "updated_at": status.get("updated_at", run_meta.get("created_at", "")),
                    "session_dir": str(session_dir),
                    "mtime": mtime,
                }
            )
    items.sort(key=lambda item: float(item.get("mtime", 0.0)), reverse=True)
    return items[: max(1, min(int(limit), 200))]


def get_review_session(settings, run_id: str, session_id: str) -> dict[str, Any]:
    run_dir = run_service.runtime_run_dir_by_id(settings, run_id)
    if not isinstance(run_dir, Path):
        raise ValueError(f"run_id not found in runtime_workspaces: {run_id}")
    session_dir = _session_dir(run_dir, session_id)
    if not session_dir.is_dir():
        raise ValueError(f"review session not found: {run_id}/{session_id}")
    return {
        "run_meta": _read_json_if_exists(session_dir / "run_meta.json") or {},
        "session_status": _read_json_if_exists(session_dir / "session_status.json") or {},
        "consensus_report": _read_json_if_exists(session_dir / "consensus_report.json") or {},
    }
