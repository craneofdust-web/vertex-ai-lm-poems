from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.main import app


def _ensure_generation_dependencies() -> bool:
    try:
        import vertexai  # noqa: F401
    except ModuleNotFoundError:
        print("[error] Missing dependency: vertexai")
        print("[hint] Install backend requirements in the active Python environment:")
        print("  python3 -m pip install -r requirements-pipeline.txt")
        return False
    return True


def _count_markdown_files(source_folder: Path) -> int:
    if not source_folder.exists() or not source_folder.is_dir():
        return 0
    try:
        return sum(1 for _ in source_folder.rglob("*.md"))
    except OSError:
        return 0


def _warn_if_low_coverage_full(mode: str, body: dict[str, object]) -> None:
    if mode != "full":
        return
    iterations = int(body.get("iterations") or 0)
    sample_size = int(body.get("sample_size") or 0)
    if iterations <= 0 or sample_size <= 0:
        print("[info] full run uses backend default coverage profile (recommended for v0.3.1).")
        return

    estimated_draws = iterations * sample_size
    source_hint = str(body.get("source_folder") or os.getenv("POEMS_SOURCE_FOLDER", "")).strip()
    corpus_markdown_files = 0
    if source_hint:
        corpus_markdown_files = _count_markdown_files(Path(source_hint).expanduser())

    if corpus_markdown_files > 0 and estimated_draws < corpus_markdown_files:
        print(
            f"[warn] low coverage config: iterations*sample_size={estimated_draws} "
            f"< corpus_markdown_files={corpus_markdown_files}. "
            "For large corpora, this usually under-covers cited sources."
        )
        return
    if estimated_draws < 500:
        print(
            f"[warn] low coverage config: iterations*sample_size={estimated_draws}. "
            "For 500+ corpus targets, prefer draws >= 500."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trigger /run/smoke or /run/full and persist response JSON.")
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--iterations", type=int, default=0)
    parser.add_argument("--sample-size", type=int, default=0)
    parser.add_argument("--max-stage-jump", type=int, default=2)
    parser.add_argument("--project-id", default="")
    parser.add_argument("--location", default="")
    parser.add_argument("--model-candidates", default="")
    parser.add_argument("--source-folder", default="")
    parser.add_argument("--skip-fill", action="store_true")
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not _ensure_generation_dependencies():
        raise SystemExit(1)

    body: dict[str, object] = {}
    if args.iterations > 0:
        body["iterations"] = args.iterations
    if args.sample_size > 0:
        body["sample_size"] = args.sample_size
    if args.max_stage_jump > 0:
        body["max_stage_jump"] = args.max_stage_jump
    if args.project_id:
        body["project_id"] = args.project_id
    if args.location:
        body["location"] = args.location
    if args.model_candidates:
        body["model_candidates"] = args.model_candidates
    if args.source_folder:
        body["source_folder"] = args.source_folder
    if args.skip_fill:
        body["skip_fill"] = True

    endpoint = "/run/full" if args.mode == "full" else "/run/smoke"
    print(f"[{datetime.now().isoformat(timespec='seconds')}] start {endpoint}")
    print(f"payload={json.dumps(body, ensure_ascii=False)}")
    _warn_if_low_coverage_full(args.mode, body)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(endpoint, json=body)
    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": response.text}

    out_path = (
        Path(args.out)
        if args.out
        else Path(f"{args.mode}_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"status_code={response.status_code}")
    run_id = payload.get("ingest", {}).get("run_id") if isinstance(payload, dict) else ""
    print(f"run_id={run_id}")
    print(f"result_file={out_path}")
    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        print(f"[error] API returned {response.status_code}: {detail}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
