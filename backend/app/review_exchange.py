from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .review_sessions import DEFAULT_WAVE_IDS, POLICY_VERSION, REVIEWER_MODE, utc_now
from .review_sources import resolve_review_source
from .services import run_service


CONTRACT_VERSION = "review-exchange-v0.1"
STANCE_CHOICES = {"support", "revise", "reject"}
STANCE_ALIASES = {
    "balanced": "revise",
    "supportive": "support",
    "supportive_diagnostic": "support",
    "support_with_caution": "support",
    "supportive_critical": "support",
    "diagnostic": "revise",
    "diagnostic_revise": "revise",
    "mixed": "revise",
    "skeptical": "revise",
    "constructive": "revise",
    "constructive_critical": "revise",
    "skeptical_reject": "reject",
    "qualified_positive": "support",
    "qualified_positive_as_workbench_experiment": "support",
    "qualified_praise": "support",
    "qualified_pass": "support",
    "positive": "support",
    "positive_with_reservations": "support",
    "positive_with_revision_focus": "support",
    "positive_with_minor_reservations": "support",
    "positive_with_targeted_revisions": "support",
    "positive_with_targeted_revision_notes": "support",
    "positive_with_formal_reservations": "support",
    "positive_with_craft_reservations": "support",
    "positive_with_required_formal_revision": "support",
    "affirmative_with_minor_reservations": "support",
    "affirming_with_reservations": "support",
    "affirming_with_precise_revision": "support",
    "accept_with_reservations": "support",
    "accept_with_notes": "support",
    "accept_with_revision": "support",
    "accept_with_revision_focus": "support",
    "accept_general_pool": "support",
    "accept_general_pool_with_notes": "support",
    "accept_general_pool_with_reservations": "support",
    "advance_with_notes": "support",
    "advance_with_guidance": "support",
    "advance_with_reservations": "support",
    "advance_with_revision": "support",
    "encouraging": "support",
    "encouraging_refine": "support",
    "encouraging_with_revision_targets": "support",
    "encouraging_with_targeted_revision": "support",
    "encouraging_with_targeted_revisions": "support",
    "encouraging_with_targeted_craft_notes": "support",
    "encouraging_with_reservations": "support",
    "encouraging_with_craft_focus": "support",
    "encouraging_with_clear_craft_flags": "support",
    "promising": "support",
    "promising_fragment": "support",
    "promising_revision": "support",
    "promising_transition": "support",
    "promising_experiment": "support",
    "promising_apprenticeship": "support",
    "promising_apprentice": "support",
    "promising_early_archive": "support",
    "promising_early_experiment": "support",
    "promising_early_seed": "support",
    "supportive_positive": "support",
    "supportive_refinement": "support",
    "supportive_constructive": "support",
    "cautiously_positive": "support",
    "guardedly_positive": "support",
    "measured_positive": "support",
    "highly_favorable": "support",
    "mostly_positive": "support",
    "pass": "support",
    "pass_with_notes": "support",
    "pass_with_reservations": "support",
    "pass_with_revision_notes": "support",
    "pass_with_targeted_revision": "support",
    "salon_ready_with_minor_refinement_notes": "support",
    "mixed_positive": "support",
    "mixed_positive_with_structural_reservations": "support",
    "mixed_reservation": "revise",
    "mixed_with_reservations": "revise",
    "qualified_hold": "revise",
    "retain_and_develop": "revise",
}
LIST_FIELDS = (
    "what_works",
    "what_is_being_tested",
    "structural_gaps",
    "do_not_judge_harshly",
    "anticipated_later_work",
)
WAVE_FOCUS = {
    "craft_pass": "Focus on line movement, form, sonic pressure, and structural handling.",
    "theme_pass": "Focus on thematic field, symbol logic, worldview, and semantic coherence.",
    "counter_reading_pass": "Act as the skeptical reader who checks overclaim, flattening, and weak evidence.",
    "revision_synthesis_pass": "Produce revision-oriented synthesis that respects maturity stage and does not erase live experimentation.",
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            out.append(payload)
    return out


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def _session_dir(settings, run_id: str, session_id: str) -> Path:
    run_dir = run_service.runtime_run_dir_by_id(settings, run_id)
    if not isinstance(run_dir, Path):
        raise ValueError(f"run_id not found in runtime_workspaces: {run_id}")
    return run_dir.parent.parent / "literary_salon" / session_id


def review_contract() -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "wave_ids": list(DEFAULT_WAVE_IDS),
        "required_fields": {
            "target_id": "string",
            "stance": "support|revise|reject",
            "confidence": "float between 0 and 1",
            "what_works": "list[string]",
            "what_is_being_tested": "list[string]",
            "structural_gaps": "list[string]",
            "do_not_judge_harshly": "list[string]",
            "anticipated_later_work": "list[string]",
            "rationale": "string",
        },
        "notes": [
            "Return JSON only for each target, with no markdown wrapper.",
            "Judge poems within their maturity bucket and comparison policy.",
            "Ground claims in the poem text and current graph anchors.",
        ],
    }


def _coerce_text_list(payload: dict[str, Any], key: str, limit: int = 4) -> list[str]:
    raw = payload.get(key)
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError(f"{key} must be a string or list of strings")
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _normalize_stance(raw_value: Any) -> str:
    stance = str(raw_value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if stance in STANCE_CHOICES:
        return stance
    if stance in STANCE_ALIASES:
        return STANCE_ALIASES[stance]
    if "reject" in stance:
        return "reject"
    if "support" in stance:
        return "support"
    if any(token in stance for token in ("positive", "affirm", "accept", "advance", "pass", "promising", "encourag", "favorable", "qualified_praise", "qualified_positive", "cautious", "guarded", "measured")):
        return "support"
    if any(token in stance for token in ("保留", "肯定", "正向", "看好", "可取", "可用", "鼓勵", "通過")):
        return "support"
    if any(token in stance for token in ("withhold", "defer", "insufficient", "hold", "暫緩", "保留判斷", "不通過", "否決", "拒絕")):
        return "reject"
    if any(token in stance for token in ("revise", "diagnostic", "mixed", "skeptical", "construct", "critical")):
        return "revise"
    if any(token in stance for token in ("revision", "refine", "refinement", "reservation", "reserve", "note", "guidance", "tighten", "rework", "修", "調整", "修改", "保留")):
        return "revise"
    return "revise" if stance else ""


def _base_system_prompt(wave_id: str) -> str:
    focus = WAVE_FOCUS.get(wave_id, "Review the poem carefully according to the assigned rubric.")
    return (
        "You are a literary salon reviewer working on a poetry-development corpus. "
        "You must evaluate one poem at a time, respecting its maturity stage and comparison policy. "
        "Do not flatten unfinished work against mature late work. "
        f"{focus} Return exactly one JSON object and no markdown."
    )


def build_prompt_job(target: dict[str, Any], wave_id: str, batch_id: str) -> dict[str, Any]:
    if wave_id not in DEFAULT_WAVE_IDS:
        raise ValueError(f"unsupported wave_id: {wave_id}")
    payload = {
        "target_id": target["target_id"],
        "title": target["title"],
        "source_id": target["source_id"],
        "folder_status": target["folder_status"],
        "completion_status": target["completion_status"],
        "creation_time_hint": target["creation_time_hint"],
        "creation_time_hint_source": target["creation_time_hint_source"],
        "maturity_bucket": target["maturity_bucket"],
        "comparison_policy": target["comparison_policy"],
        "review_mode": target["review_mode"],
        "match_count": target["match_count"],
        "matched_nodes": target.get("matched_nodes", []),
        "author_context_flags": target.get("author_context_flags", {}),
        "text_metrics": target.get("text_metrics", {}),
        "full_text": target.get("full_text", ""),
    }
    user_prompt = (
        "Review this poem as one unit of the literary salon workflow.\n\n"
        f"Wave: {wave_id}\n"
        f"Batch: {batch_id}\n"
        f"Contract version: {CONTRACT_VERSION}\n\n"
        "Output one JSON object with these keys exactly: "
        "target_id, stance, confidence, what_works, what_is_being_tested, structural_gaps, "
        "do_not_judge_harshly, anticipated_later_work, rationale.\n\n"
        "Poem packet:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return {
        "custom_id": f"{wave_id}:{batch_id}:{target['target_id']}",
        "target_id": target["target_id"],
        "wave_id": wave_id,
        "batch_id": batch_id,
        "contract_version": CONTRACT_VERSION,
        "response_schema": review_contract()["required_fields"],
        "messages": [
            {"role": "system", "content": _base_system_prompt(wave_id)},
            {"role": "user", "content": user_prompt},
        ],
    }


def export_wave_prompts(
    settings,
    run_id: str,
    session_id: str,
    wave_id: str,
    batch_id: str | None = None,
) -> dict[str, Any]:
    session_dir = _session_dir(settings, run_id, session_id)
    batches_dir = session_dir / "review_batches"
    if not batches_dir.is_dir():
        raise ValueError(f"review_batches not found: {batches_dir}")
    if batch_id:
        requested_batch = str(batch_id).strip()
        batch_path = batches_dir / f"{requested_batch}.jsonl"
        if not batch_path.is_file():
            raise ValueError(f"batch_id not found: {requested_batch}")
        batch_paths = [batch_path]
    else:
        batch_paths = sorted(batches_dir.glob("batch_*.jsonl"))
    if not batch_paths:
        raise ValueError("no batch files found")

    export_root = session_dir / "prompt_exports" / wave_id
    contract_path = export_root / "contract.json"
    _write_json(contract_path, review_contract())
    batch_summaries: list[dict[str, Any]] = []
    total_jobs = 0
    for path in batch_paths:
        targets = _load_jsonl(path)
        batch_name = path.stem
        jobs = [build_prompt_job(target, wave_id=wave_id, batch_id=batch_name) for target in targets]
        out_path = export_root / f"{batch_name}.prompts.jsonl"
        _write_jsonl(out_path, jobs)
        batch_summaries.append({"batch_id": batch_name, "prompt_file": str(out_path), "job_count": len(jobs)})
        total_jobs += len(jobs)
    return {
        "run_id": run_id,
        "session_id": session_id,
        "wave_id": wave_id,
        "batch_count": len(batch_summaries),
        "job_count": total_jobs,
        "contract_file": str(contract_path),
        "batches": batch_summaries,
    }


def _extract_target_id(payload: dict[str, Any]) -> str:
    target_id = str(payload.get("target_id") or "").strip()
    if target_id:
        return target_id
    custom_id = str(payload.get("custom_id") or "").strip()
    if custom_id.count(":") >= 2:
        return custom_id.split(":", 2)[2]
    return ""


def validate_review_record(
    target: dict[str, Any],
    wave_id: str,
    batch_id: str,
    payload: dict[str, Any],
    provider: str = "external-gpt",
    model: str = "",
) -> dict[str, Any]:
    record = payload.get("review") if isinstance(payload.get("review"), dict) else payload
    if not isinstance(record, dict):
        raise ValueError("review payload must be an object")
    target_id = _extract_target_id(record)
    if not target_id:
        target_id = _extract_target_id(payload)
    if target_id != target["target_id"]:
        raise ValueError(f"target_id mismatch: expected {target['target_id']} got {target_id or '<missing>'}")

    stance = _normalize_stance(record.get("stance"))
    if stance not in STANCE_CHOICES:
        raise ValueError(f"stance must be one of {sorted(STANCE_CHOICES)}")
    try:
        confidence = float(record.get("confidence", 0.0))
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence must be numeric") from exc
    confidence = max(0.0, min(1.0, confidence))
    rationale = str(record.get("rationale") or "").strip()
    if not rationale:
        raise ValueError("rationale is required")

    normalized = {
        "wave_id": wave_id,
        "provider": str(record.get("provider") or provider).strip(),
        "model": str(record.get("model") or model).strip(),
        "policy_version": POLICY_VERSION,
        "reviewer_mode": REVIEWER_MODE,
        "batch_id": batch_id,
        "target_id": target["target_id"],
        "timestamp": str(record.get("timestamp") or utc_now()),
        "review_mode": target["review_mode"],
        "maturity_bucket": target["maturity_bucket"],
        "comparison_policy": target["comparison_policy"],
        "stance": stance,
        "confidence": round(confidence, 2),
        "rationale": rationale,
        "title": target["title"],
        "source_id": target["source_id"],
        "match_count": int(target.get("match_count", 0) or 0),
        "top_nodes": [
            str(item.get("node_name") or item.get("node_id") or "").strip()
            for item in target.get("matched_nodes", [])[:3]
            if str(item.get("node_name") or item.get("node_id") or "").strip()
        ],
    }
    normalized.update(resolve_review_source(normalized["provider"], normalized["model"]))
    for key in LIST_FIELDS:
        normalized[key] = _coerce_text_list(record, key)
    return normalized


def import_wave_results(
    settings,
    run_id: str,
    session_id: str,
    wave_id: str,
    input_path: Path,
    batch_id: str,
    provider: str = "external-gpt",
    model: str = "",
    allow_partial: bool = False,
) -> dict[str, Any]:
    session_dir = _session_dir(settings, run_id, session_id)
    batch_path = session_dir / "review_batches" / f"{batch_id}.jsonl"
    if not batch_path.is_file():
        raise ValueError(f"batch file not found: {batch_path}")
    targets = _load_jsonl(batch_path)
    target_by_id = {item["target_id"]: item for item in targets}
    imported_rows = _load_jsonl(input_path)
    if not imported_rows:
        raise ValueError(f"no JSONL rows found in {input_path}")

    normalized_by_id: dict[str, dict[str, Any]] = {}
    for payload in imported_rows:
        target_id = _extract_target_id(payload)
        if not target_id:
            inner = payload.get("review") if isinstance(payload.get("review"), dict) else {}
            target_id = _extract_target_id(inner) if isinstance(inner, dict) else ""
        if target_id not in target_by_id:
            raise ValueError(f"imported target_id not present in batch {batch_id}: {target_id}")
        normalized = validate_review_record(
            target=target_by_id[target_id],
            wave_id=wave_id,
            batch_id=batch_id,
            payload=payload,
            provider=provider,
            model=model,
        )
        normalized_by_id[target_id] = normalized

    output_path = session_dir / "review_waves" / wave_id / f"{batch_id}.jsonl"
    existing_rows = _load_jsonl(output_path)
    existing_by_id = {str(row.get("target_id") or "").strip(): row for row in existing_rows if row.get("target_id")}
    existing_by_id.update(normalized_by_id)
    if not allow_partial and len(existing_by_id) < len(target_by_id):
        missing = sorted(set(target_by_id) - set(existing_by_id))
        raise ValueError(f"batch {batch_id} still missing {len(missing)} targets; rerun with --allow-partial if intended")
    merged_rows = [existing_by_id[target_id] for target_id in sorted(existing_by_id)]
    _write_jsonl(output_path, merged_rows)
    return {
        "run_id": run_id,
        "session_id": session_id,
        "wave_id": wave_id,
        "batch_id": batch_id,
        "imported_count": len(normalized_by_id),
        "final_count": len(merged_rows),
        "output_path": str(output_path),
    }
