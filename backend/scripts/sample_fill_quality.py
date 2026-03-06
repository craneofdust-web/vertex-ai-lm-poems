from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.db import db_session
from app.ingest import source_text_by_id


def _read_json_if_exists(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _mount_match_count(row: Any) -> int:
    if not isinstance(row, dict):
        return 0
    raw = row.get("match_count")
    if raw is None:
        nodes = row.get("matched_nodes")
        if isinstance(nodes, list):
            raw = len(nodes)
        else:
            raw = 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def _mounting_totals(run_dir: Path, filename: str) -> dict[str, int]:
    payload = _read_json_if_exists(run_dir / filename)
    if not isinstance(payload, list):
        return {"poems_total": 0, "total_matches": 0}
    return {
        "poems_total": len(payload),
        "total_matches": sum(_mount_match_count(row) for row in payload),
    }


def _collect_runtime_run_dirs(settings) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for run_dir in settings.runtime_root.glob("*/runs/*"):
        if not run_dir.is_dir():
            continue
        if not (run_dir / "master_skill_web.json").is_file():
            continue
        try:
            mtime = float(run_dir.stat().st_mtime)
        except OSError:
            continue
        run_id = run_dir.name
        entries.append(
            {
                "run_id": run_id,
                "run_dir": run_dir,
                "mode": (
                    "full"
                    if run_id.startswith("run_full_")
                    else "smoke"
                    if run_id.startswith("run_smoke_")
                    else "other"
                ),
                "mtime": mtime,
            }
        )
    entries.sort(key=lambda item: float(item["mtime"]), reverse=True)
    return entries


def _default_run_id(settings) -> str:
    entries = _collect_runtime_run_dirs(settings)
    if not entries:
        return ""
    for preferred_mode in ("full", "smoke", "other"):
        for item in entries:
            if str(item.get("mode")) == preferred_mode:
                return str(item["run_id"])
    return str(entries[0]["run_id"])


def _runtime_run_dir(settings, run_id: str) -> Path | None:
    for item in _collect_runtime_run_dirs(settings):
        if str(item["run_id"]) == run_id:
            run_dir = item.get("run_dir")
            if isinstance(run_dir, Path):
                return run_dir
    return None


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _canonicalize(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", text, flags=re.UNICODE).lower()


def _quote_in_source(quote: str, source: str) -> bool:
    q = str(quote or "").strip()
    s = str(source or "")
    if not q or not s:
        return False
    if q in s:
        return True
    if _normalize_whitespace(q) in _normalize_whitespace(s):
        return True
    qn = _canonicalize(q)
    sn = _canonicalize(s)
    return bool(qn) and qn in sn


def _excerpt(source: str, quote: str, radius: int = 120) -> str:
    src = str(source or "")
    q = str(quote or "").strip()
    if not src:
        return ""
    if not q:
        return src[: radius * 2]
    idx = src.find(q)
    if idx < 0:
        return src[: radius * 2]
    start = max(0, idx - radius)
    end = min(len(src), idx + len(q) + radius)
    return src[start:end]


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Sample fill assignments for manual quality review before promoting into citations."
    )
    parser.add_argument(
        "--run-id",
        default=_default_run_id(settings),
        help="Run id. Defaults to latest runtime run.",
    )
    parser.add_argument("--sample-size", type=int, default=40, help="How many matches to sample.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for stable sampling.")
    parser.add_argument(
        "--out-prefix",
        default="logs/fill_quality",
        help="Output prefix (without extension). Writes .json and .md",
    )
    return parser.parse_args()


def _source_folder_from_db(run_id: str, settings) -> Path:
    with db_session() as conn:
        row = conn.execute("SELECT config_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row and row["config_json"]:
        try:
            config = json.loads(row["config_json"])
        except json.JSONDecodeError:
            config = {}
        source_folder = Path(str(config.get("source_folder", "")).strip()).expanduser()
        if source_folder and source_folder.exists():
            return source_folder
    return settings.source_folder


def _load_assignments(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "fill_assignments.json"
    if not path.is_file():
        raise FileNotFoundError(f"fill_assignments.json not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("fill_assignments.json must be a JSON array")
    return payload


def _flatten(assignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in assignments:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("source_id", "")).strip()
        matches = row.get("matches")
        if not source_id or not isinstance(matches, list):
            continue
        for idx, match in enumerate(matches):
            if not isinstance(match, dict):
                continue
            out.append(
                {
                    "source_id": source_id,
                    "match_index": idx,
                    "node_id": str(match.get("node_id", "")).strip(),
                    "node_name": str(match.get("node_name", "")).strip(),
                    "node_tier": str(match.get("node_tier", "")).strip(),
                    "quote": str(match.get("quote", "")).strip(),
                    "why": str(match.get("why", "")).strip(),
                    "confidence": float(match.get("confidence", 0.0) or 0.0),
                    "evidence_type": str(match.get("evidence_type", "")).strip(),
                    "source": str(match.get("source", "")).strip(),
                }
            )
    return out


def _choose_samples(rows: list[dict[str, Any]], sample_size: int, seed: int) -> list[dict[str, Any]]:
    if sample_size <= 0 or not rows:
        return []
    bad = [row for row in rows if not bool(row.get("quote_in_source"))]
    low = [row for row in rows if bool(row.get("quote_in_source")) and float(row.get("confidence", 0.0)) < 0.8]
    good = [row for row in rows if bool(row.get("quote_in_source")) and float(row.get("confidence", 0.0)) >= 0.8]

    rng = random.Random(seed)
    rng.shuffle(bad)
    rng.shuffle(low)
    rng.shuffle(good)
    ordered = bad + low + good
    return ordered[: min(sample_size, len(ordered))]


def _to_markdown(report: dict[str, Any]) -> str:
    stats = report["stats"]
    lines = [
        "# Fill Quality Sample Review",
        "",
        f"- run_id: `{report['run_id']}`",
        f"- source_folder: `{report['source_folder']}`",
        f"- full_matches_from_poem_mounting_full: `{stats['full_matches_from_poem_mounting_full']}`",
        f"- seed_matches_from_poem_mounting_seed: `{stats['seed_matches_from_poem_mounting_seed']}`",
        f"- fill_matches_from_fill_assignments: `{stats['fill_matches_from_fill_assignments']}`",
        f"- seed_plus_fill_matches: `{stats['seed_plus_fill_matches']}`",
        f"- full_minus_seed_matches: `{stats['full_minus_seed_matches']}`",
        f"- fill_vs_full_minus_seed_delta: `{stats['fill_vs_full_minus_seed_delta']}`",
        f"- quote_in_source_count: `{stats['quote_in_source_count']}`",
        f"- quote_in_source_rate_percent: `{stats['quote_in_source_rate_percent']}`",
        f"- sampled: `{len(report['samples'])}`",
        "",
    ]

    for i, row in enumerate(report["samples"], start=1):
        lines.extend(
            [
                f"## Sample {i}",
                f"- source_id: `{row['source_id']}`",
                f"- node: `{row['node_id']}` ({row['node_name']})",
                f"- confidence: `{row['confidence']}`",
                f"- quote_in_source: `{row['quote_in_source']}`",
                "",
                "### quote",
                "```text",
                row["quote"] or "(empty)",
                "```",
                "",
                "### excerpt",
                "```text",
                row["source_excerpt"] or "(no excerpt)",
                "```",
                "",
                "### why",
                row["why"] or "(empty)",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    args = parse_args()
    settings = get_settings()
    run_id = str(args.run_id).strip()
    if not run_id:
        raise SystemExit("[error] no run_id available")
    run_dir = _runtime_run_dir(settings, run_id)
    if not isinstance(run_dir, Path):
        raise SystemExit(f"[error] run_id not found in runtime_workspaces: {run_id}")

    source_folder = _source_folder_from_db(run_id, settings)
    assignments = _load_assignments(run_dir)
    rows = _flatten(assignments)
    seed_totals = _mounting_totals(run_dir, "poem_mounting_seed.json")
    full_totals = _mounting_totals(run_dir, "poem_mounting_full.json")

    source_cache: dict[str, str] = {}
    for row in rows:
        source_id = str(row["source_id"])
        if source_id not in source_cache:
            source_cache[source_id] = source_text_by_id(source_folder, source_id)
        source_text = source_cache[source_id]
        quote = str(row["quote"])
        row["quote_in_source"] = _quote_in_source(quote, source_text)
        row["source_excerpt"] = _excerpt(source_text, quote)

    total = len(rows)
    in_source = sum(1 for row in rows if bool(row.get("quote_in_source")))
    seed_matches = int(seed_totals["total_matches"])
    full_matches = int(full_totals["total_matches"])
    seed_plus_fill = seed_matches + total
    full_minus_seed = max(0, full_matches - seed_matches)
    report = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "source_folder": str(source_folder),
        "stats": {
            "seed_poems_from_poem_mounting_seed": int(seed_totals["poems_total"]),
            "full_poems_from_poem_mounting_full": int(full_totals["poems_total"]),
            "seed_matches_from_poem_mounting_seed": seed_matches,
            "full_matches_from_poem_mounting_full": full_matches,
            "fill_matches_from_fill_assignments": total,
            "seed_plus_fill_matches": seed_plus_fill,
            "full_minus_seed_matches": full_minus_seed,
            "fill_vs_full_minus_seed_delta": int(total - full_minus_seed),
            "quote_in_source_count": in_source,
            "quote_in_source_rate_percent": round((in_source * 100.0) / total, 2) if total else 0.0,
            "invalid_quote_count": max(0, total - in_source),
        },
        "samples": _choose_samples(rows, sample_size=max(1, int(args.sample_size)), seed=int(args.seed)),
    }

    out_prefix = Path(args.out_prefix).expanduser()
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_json = out_prefix.with_suffix(".json")
    out_md = out_prefix.with_suffix(".md")
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(_to_markdown(report), encoding="utf-8")

    print(f"[ok] wrote {out_json}")
    print(f"[ok] wrote {out_md}")
    print(
        "[summary] "
        f"seed_matches={report['stats']['seed_matches_from_poem_mounting_seed']} | "
        f"fill_matches={report['stats']['fill_matches_from_fill_assignments']} | "
        f"full_matches={report['stats']['full_matches_from_poem_mounting_full']} | "
        f"fill_vs_full_minus_seed_delta={report['stats']['fill_vs_full_minus_seed_delta']} | "
        f"quote_in_source_rate_percent={report['stats']['quote_in_source_rate_percent']} | "
        f"invalid_quote_count={report['stats']['invalid_quote_count']}"
    )


if __name__ == "__main__":
    main()
