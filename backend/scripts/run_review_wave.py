from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.review_sessions import run_review_wave


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one literary salon review wave over exported batches.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument(
        "--wave-id",
        required=True,
        choices=["craft_pass", "theme_pass", "counter_reading_pass", "revision_synthesis_pass"],
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_review_wave(
        settings=get_settings(),
        run_id=str(args.run_id).strip(),
        session_id=str(args.session_id).strip(),
        wave_id=str(args.wave_id).strip(),
        force=bool(args.force),
    )
    print(f"[ok] wave_id={result['wave_id']}")
    print(f"[ok] batch_count={result['batch_count']}")
    print(f"[ok] review_count={result['review_count']}")


if __name__ == "__main__":
    main()
