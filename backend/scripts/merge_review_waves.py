from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.review_sessions import merge_review_waves


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge literary salon review waves into one consensus report.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session-id", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = merge_review_waves(
        settings=get_settings(),
        run_id=str(args.run_id).strip(),
        session_id=str(args.session_id).strip(),
    )
    overview = report.get("overview", {})
    aggregate = report.get("aggregate", {})
    print(f"[ok] run_id={overview.get('run_id', '')}")
    print(f"[ok] session_id={overview.get('session_id', '')}")
    print(f"[ok] target_count={overview.get('target_count', 0)}")
    print(f"[ok] consensus_counts={aggregate.get('consensus_counts', {})}")


if __name__ == "__main__":
    main()
