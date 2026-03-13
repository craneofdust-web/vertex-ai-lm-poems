from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.review_exchange import import_wave_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import one externally generated review-wave batch into the salon session.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--wave-id", required=True, choices=["craft_pass", "theme_pass", "counter_reading_pass", "revision_synthesis_pass"])
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--provider", default="external-gpt")
    parser.add_argument("--model", default="")
    parser.add_argument("--allow-partial", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = import_wave_results(
        settings=get_settings(),
        run_id=str(args.run_id).strip(),
        session_id=str(args.session_id).strip(),
        wave_id=str(args.wave_id).strip(),
        input_path=Path(str(args.input)).expanduser(),
        batch_id=str(args.batch_id).strip(),
        provider=str(args.provider).strip(),
        model=str(args.model).strip(),
        allow_partial=bool(args.allow_partial),
    )
    print(f"[ok] wave_id={result['wave_id']}")
    print(f"[ok] batch_id={result['batch_id']}")
    print(f"[ok] imported_count={result['imported_count']}")
    print(f"[ok] final_count={result['final_count']}")
    print(f"[ok] output_path={result['output_path']}")


if __name__ == "__main__":
    main()
