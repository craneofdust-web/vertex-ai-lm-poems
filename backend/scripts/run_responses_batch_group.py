from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER_PATH = SCRIPT_DIR / "run_responses_wave.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multiple review batches sequentially for one relay wave")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--wave-id", required=True, choices=["craft_pass", "theme_pass", "counter_reading_pass", "revision_synthesis_pass"])
    parser.add_argument("--model", default="gpt-5.3-codex")
    parser.add_argument("--reasoning-effort", default="xhigh")
    parser.add_argument("--provider-label", default="中轉站_leishen_gpt")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--max-jobs", type=int, default=0)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--base-url-file", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-file", default="")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all-batches", action="store_true")
    parser.add_argument("batch_ids", nargs="*")
    return parser.parse_args()


def discover_batches(repo_root: Path, run_id: str, session_id: str) -> list[str]:
    review_batches = repo_root / "runtime_workspaces" / run_id / "literary_salon" / session_id / "review_batches"
    if not review_batches.is_dir():
        raise SystemExit(f"[error] review_batches not found: {review_batches}")
    return [path.stem for path in sorted(review_batches.glob("batch_*.jsonl"))]


def main() -> int:
    args = parse_args()
    repo_root = SCRIPT_DIR.parent.parent
    batch_ids = list(args.batch_ids)
    if args.all_batches:
        batch_ids = discover_batches(repo_root, str(args.run_id).strip(), str(args.session_id).strip())
    if not batch_ids:
        raise SystemExit("[error] no batch ids provided; pass --all-batches or one/more batch_ids")

    completed: list[str] = []
    failed: list[dict[str, object]] = []
    for batch_id in batch_ids:
        command = [
            sys.executable,
            str(RUNNER_PATH),
            "--run-id",
            str(args.run_id).strip(),
            "--session-id",
            str(args.session_id).strip(),
            "--wave-id",
            str(args.wave_id).strip(),
            "--batch-id",
            str(batch_id).strip(),
            "--model",
            str(args.model).strip(),
            "--reasoning-effort",
            str(args.reasoning_effort).strip(),
            "--provider-label",
            str(args.provider_label).strip(),
            "--timeout",
            str(float(args.timeout)),
            "--sleep-seconds",
            str(float(args.sleep_seconds)),
        ]
        if int(args.max_jobs) > 0:
            command.extend(["--max-jobs", str(int(args.max_jobs))])
        if str(args.base_url).strip():
            command.extend(["--base-url", str(args.base_url).strip()])
        if str(args.base_url_file).strip():
            command.extend(["--base-url-file", str(args.base_url_file).strip()])
        if str(args.api_key).strip():
            command.extend(["--api-key", str(args.api_key).strip()])
        if str(args.api_key_file).strip():
            command.extend(["--api-key-file", str(args.api_key_file).strip()])
        if args.dry_run:
            command.append("--dry-run")

        print(f"[group] start {args.wave_id} {batch_id}")
        result = subprocess.run(command, cwd=str(repo_root))
        if result.returncode == 0:
            completed.append(str(batch_id).strip())
            continue
        failed.append({"batch_id": str(batch_id).strip(), "exit_code": int(result.returncode)})
        if not args.continue_on_error:
            break

    summary = {
        "run_id": str(args.run_id).strip(),
        "session_id": str(args.session_id).strip(),
        "wave_id": str(args.wave_id).strip(),
        "requested_batches": batch_ids,
        "completed_batches": completed,
        "failed_batches": failed,
        "dry_run": bool(args.dry_run),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
