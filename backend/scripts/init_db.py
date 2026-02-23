from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.db import db_session, init_db
from app.ingest import ingest_run_artifacts


def _detect_default_runtime_run(settings) -> tuple[Path | None, str | None]:
    run_dirs = []
    for run_dir in settings.runtime_root.glob("*/runs/*"):
        if not run_dir.is_dir():
            continue
        if not (run_dir / "master_skill_web.json").is_file():
            continue
        run_dirs.append(run_dir)
    if not run_dirs:
        return None, None

    full_runs = [run_dir for run_dir in run_dirs if run_dir.name.startswith("run_full_")]
    pool = full_runs if full_runs else run_dirs
    latest = max(pool, key=lambda path: path.stat().st_mtime)
    return latest.resolve(), latest.name


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    default_run_dir, default_run_id = _detect_default_runtime_run(settings)
    parser = argparse.ArgumentParser(description="Initialize SQLite schema and optionally import a run directory.")
    parser.add_argument(
        "--run-dir",
        default=str(default_run_dir) if default_run_dir else "",
        help="Path to a runtime run directory containing master_skill_web.json",
    )
    parser.add_argument(
        "--run-id",
        default=default_run_id or "",
        help="Run id to store in SQLite.",
    )
    parser.add_argument("--model-used", default=settings.default_model_candidates.split(",")[0].strip())
    parser.add_argument("--iterations", type=int, default=0)
    parser.add_argument("--sample-size", type=int, default=0)
    parser.add_argument("--max-stage-jump", type=int, default=settings.default_max_stage_jump)
    parser.add_argument("--source-folder", default=str(settings.source_folder))
    parser.add_argument("--skip-import", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    init_db()
    print(f"[ok] initialized schema at {settings.db_path}")
    if args.skip_import:
        return

    if not str(args.run_dir).strip():
        print("[warn] no runtime run detected under runtime_workspaces; skipping import")
        return

    run_dir = Path(args.run_dir).expanduser().resolve()
    run_id = str(args.run_id).strip() or run_dir.name
    source_folder = Path(args.source_folder).expanduser().resolve()
    if not run_dir.exists():
        print(f"[warn] run-dir not found, skipping import: {run_dir}")
        return

    with db_session() as conn:
        summary = ingest_run_artifacts(
            conn=conn,
            run_id=run_id,
            run_dir=run_dir,
            source_folder=source_folder,
            model_used=args.model_used,
            iterations=args.iterations if args.iterations > 0 else None,
            sample_size=args.sample_size if args.sample_size > 0 else None,
            max_stage_jump=max(1, int(args.max_stage_jump)),
            config={
                "imported_via": "init_db.py",
                "pipeline_version": "v0.3",
            },
        )
    print(f"[ok] imported run {run_id}")
    print(summary)


if __name__ == "__main__":
    main()
