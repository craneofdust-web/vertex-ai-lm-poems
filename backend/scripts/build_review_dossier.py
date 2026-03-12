from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.services import run_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build per-poem review dossier with all salon opinions.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session-id", required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def session_dir_from_run(run_dir: Path, session_id: str) -> Path:
    if run_dir.parent.name == "runs":
        workspace = run_dir.parent.parent
    else:
        workspace = run_dir.parent
    return workspace / "literary_salon" / session_id


def collect_reviews(session_dir: Path, wave_ids: list[str]) -> dict[str, dict[str, dict[str, Any]]]:
    reviews_by_target: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    waves_dir = session_dir / "review_waves"
    for wave_id in wave_ids:
        wave_dir = waves_dir / wave_id
        if not wave_dir.exists():
            continue
        for batch_path in sorted(wave_dir.glob("batch_*.jsonl")):
            for review in load_jsonl(batch_path):
                target_id = str(review.get("target_id") or "").strip()
                if not target_id:
                    continue
                reviews_by_target[target_id][wave_id] = review
    return reviews_by_target


def load_legacy_mounting(run_dir: Path) -> dict[str, dict[str, Any]]:
    legacy_path = run_dir / "poem_mounting_full.json"
    records = load_json(legacy_path)
    if isinstance(records, dict):
        return {}
    legacy_by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        source_id = str(record.get("source_id") or "").strip()
        if not source_id:
            continue
        legacy_by_id[source_id] = {
            "source_id": source_id,
            "source_title": record.get("source_title"),
            "folder_status": record.get("folder_status"),
            "match_count": record.get("match_count"),
            "matched_nodes": record.get("matched_nodes", []),
        }
    return legacy_by_id


def main() -> None:
    args = parse_args()
    settings = get_settings()
    run_id = str(args.run_id).strip()
    session_id = str(args.session_id).strip()
    run_dir = run_service.runtime_run_dir_by_id(settings, run_id)
    if not isinstance(run_dir, Path):
        raise SystemExit(f"[error] run_id not found: {run_id}")
    session_dir = session_dir_from_run(run_dir, session_id)

    consensus_path = session_dir / "consensus_report.json"
    consensus = load_json(consensus_path)
    targets = consensus.get("targets", []) if isinstance(consensus, dict) else []
    if not isinstance(targets, list):
        targets = []

    run_meta = load_json(session_dir / "run_meta.json")
    wave_ids = run_meta.get("wave_ids", []) if isinstance(run_meta, dict) else []
    if not wave_ids:
        wave_ids = ["craft_pass", "theme_pass", "counter_reading_pass", "revision_synthesis_pass"]

    reviews_by_target = collect_reviews(session_dir, [str(w).strip() for w in wave_ids])
    legacy_by_id = load_legacy_mounting(run_dir)

    dossier_targets: list[dict[str, Any]] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        target_id = str(target.get("target_id") or "").strip()
        if not target_id:
            continue
        dossier_targets.append(
            {
                "target_id": target_id,
                "title": target.get("title"),
                "maturity_bucket": target.get("maturity_bucket"),
                "review_mode": target.get("review_mode"),
                "comparison_policy": target.get("comparison_policy"),
                "consensus": {
                    "status": target.get("consensus"),
                    "stance_counts": target.get("stance_counts", {}),
                    "review_count": target.get("review_count"),
                    "disagreement": target.get("disagreement"),
                    "what_works": target.get("what_works", []),
                    "what_is_being_tested": target.get("what_is_being_tested", []),
                    "structural_gaps": target.get("structural_gaps", []),
                    "do_not_judge_harshly": target.get("do_not_judge_harshly", []),
                    "anticipated_later_work": target.get("anticipated_later_work", []),
                },
                "salon_reviews": reviews_by_target.get(target_id, {}),
                "legacy_mounting": legacy_by_id.get(target_id, {}),
            }
        )

    dossier = {
        "overview": {
            "run_id": run_id,
            "session_id": session_id,
            "target_count": len(dossier_targets),
            "wave_ids": wave_ids,
        },
        "targets": dossier_targets,
    }

    output_path = session_dir / "review_dossier.json"
    output_path.write_text(json.dumps(dossier, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] review_dossier={output_path}")


if __name__ == "__main__":
    main()
