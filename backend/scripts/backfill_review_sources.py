from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.review_sources import resolve_review_source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill canonical source metadata into review_waves JSONL files.")
    parser.add_argument("--root", required=True, help="Path to literary_salon root or one session directory")
    return parser.parse_args()


def iter_jsonl_files(root: Path) -> list[Path]:
    if (root / "review_waves").is_dir():
        return sorted((root / "review_waves").glob("*/*.jsonl"))
    return sorted(root.glob("*/review_waves/*/*.jsonl"))


def main() -> None:
    args = parse_args()
    root = Path(str(args.root)).expanduser().resolve()
    files = iter_jsonl_files(root)
    updated_files = 0
    updated_rows = 0
    for path in files:
        rows = []
        changed = False
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            source = resolve_review_source(str(row.get("provider") or ""), str(row.get("model") or ""))
            for key, value in source.items():
                if row.get(key) != value:
                    row[key] = value
                    changed = True
            rows.append(row)
        if changed:
            path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
            updated_files += 1
            updated_rows += len(rows)
    print(f"[ok] updated_files={updated_files}")
    print(f"[ok] updated_rows={updated_rows}")


if __name__ == "__main__":
    main()
