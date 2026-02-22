from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.main import app


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

    client = TestClient(app)
    response = client.post(endpoint, json=body)
    payload = response.json()

    out_path = Path(args.out) if args.out else Path(f"{args.mode}_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"status_code={response.status_code}")
    run_id = payload.get("ingest", {}).get("run_id") if isinstance(payload, dict) else ""
    print(f"run_id={run_id}")
    print(f"result_file={out_path}")


if __name__ == "__main__":
    main()
