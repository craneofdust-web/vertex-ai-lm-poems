from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.db import db_session
from app.review_sessions import DEFAULT_WAVE_IDS, export_review_targets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export literary salon review targets in resumable batches.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--source-folder", default="")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    source_folder = Path(args.source_folder).expanduser() if args.source_folder else None
    with db_session() as conn:
        result = export_review_targets(
            conn=conn,
            settings=settings,
            run_id=str(args.run_id).strip(),
            session_id=str(args.session_id).strip(),
            source_folder=source_folder,
            batch_size=max(1, int(args.batch_size)),
            limit=int(args.limit) if int(args.limit) > 0 else None,
            wave_ids=DEFAULT_WAVE_IDS,
        )
    print(f"[ok] session_dir={result['session_dir']}")
    print(f"[ok] target_count={result['target_count']}")
    print(f"[ok] batch_count={result['batch_count']}")


if __name__ == "__main__":
    main()
