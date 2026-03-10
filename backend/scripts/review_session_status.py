from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.review_sessions import build_session_status, get_review_session
from app.services import run_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize one literary salon review session.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session-id", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    run_dir = run_service.runtime_run_dir_by_id(settings, str(args.run_id).strip())
    if not isinstance(run_dir, Path):
        raise SystemExit(f"[error] run_id not found in runtime_workspaces: {args.run_id}")
    session_dir = run_dir.parent.parent / "literary_salon" / str(args.session_id).strip()
    status = build_session_status(session_dir)
    payload = get_review_session(settings, str(args.run_id).strip(), str(args.session_id).strip())
    print(json.dumps({"status": status, "overview": payload.get("run_meta", {})}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
