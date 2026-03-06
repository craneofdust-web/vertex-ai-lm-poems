from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.audit import build_run_audit
from app.config import get_settings
from app.db import db_session


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


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Audit one run for corpus scan, mounting, and citation coverage.")
    parser.add_argument(
        "--run-id",
        default=_default_run_id(settings),
        help="Run id to audit. Defaults to latest runtime run.",
    )
    parser.add_argument("--out", default="", help="Optional JSON output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_id = str(args.run_id).strip()
    if not run_id:
        raise SystemExit("[error] No run_id available. Ensure runtime_workspaces contains an ingested run.")

    settings = get_settings()
    run_dir = _runtime_run_dir(settings, run_id)
    with db_session() as conn:
        report = build_run_audit(
            conn=conn,
            run_id=run_id,
            run_dir=run_dir,
            default_source_folder=settings.source_folder,
        )

    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"[ok] wrote audit to {out_path}")
    else:
        print(output)

    db_stats = report.get("db_stats", {}) if isinstance(report, dict) else {}
    mount_full = (
        report.get("runtime_artifacts", {}).get("mounting_full", {})
        if isinstance(report, dict)
        else {}
    )
    print(
        "[summary] "
        f"corpus={report.get('corpus_markdown_files', 0)} | "
        f"distinct_cited_sources={db_stats.get('distinct_cited_sources', 0)} | "
        f"citations={db_stats.get('citations', 0)} | "
        f"mounted_poems={mount_full.get('poems_with_match', 0)}/{mount_full.get('poems_total', 0)}"
    )


if __name__ == "__main__":
    main()
