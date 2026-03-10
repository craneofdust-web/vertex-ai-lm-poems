from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.relay_profile import resolve_api_key, resolve_base_url
from app.review_exchange import export_wave_prompts, import_wave_results
from app.responses_relay import append_jsonl, build_responses_payload, extract_json_object, post_responses_stream


def _load_existing_target_ids(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    existing: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            continue
        target_id = str(payload.get("target_id") or "").strip()
        if target_id:
            existing.add(target_id)
    return existing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one literary review batch against an OpenAI-compatible /responses relay.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--wave-id", required=True, choices=["craft_pass", "theme_pass", "counter_reading_pass", "revision_synthesis_pass"])
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--base-url-file", default=os.getenv("OPENAI_BASE_URL_FILE", ""))
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-file", default=os.getenv("OPENAI_API_KEY_FILE", ""))
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--reasoning-effort", default="xhigh")
    parser.add_argument("--provider-label", default="relay-openai-compatible")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--max-jobs", type=int, default=0)
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    settings = get_settings()
    export_result = export_wave_prompts(
        settings=settings,
        run_id=str(args.run_id).strip(),
        session_id=str(args.session_id).strip(),
        wave_id=str(args.wave_id).strip(),
        batch_id=str(args.batch_id).strip(),
    )
    prompt_file = Path(export_result["batches"][0]["prompt_file"])
    staging_path = prompt_file.parent / f"{Path(str(args.batch_id).strip()).stem}.responses.raw.jsonl"
    error_path = prompt_file.parent / f"{Path(str(args.batch_id).strip()).stem}.responses.errors.jsonl"
    session_dir = prompt_file.parent.parent.parent
    output_path = session_dir / "review_waves" / str(args.wave_id).strip() / f"{Path(str(args.batch_id).strip()).stem}.jsonl"
    jobs = [
        json.loads(line)
        for line in prompt_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    completed_target_ids = _load_existing_target_ids(output_path)
    if completed_target_ids:
        jobs = [job for job in jobs if str(job.get("target_id") or "").strip() not in completed_target_ids]
    if int(args.max_jobs) > 0:
        jobs = jobs[: int(args.max_jobs)]
    if args.dry_run:
        if not jobs:
            print(f"[ok] prompt_file={prompt_file}")
            print("[ok] job_count=0")
            print("[ok] all jobs already completed")
            return
        sample = build_responses_payload(jobs[0], model=str(args.model).strip(), reasoning_effort=str(args.reasoning_effort).strip())
        print(f"[ok] prompt_file={prompt_file}")
        print(f"[ok] job_count={len(jobs)}")
        print(f"[ok] sample_model={sample['model']}")
        print(f"[ok] sample_stream={sample['stream']}")
        return
    if not jobs:
        import_result = import_wave_results(
            settings=settings,
            run_id=str(args.run_id).strip(),
            session_id=str(args.session_id).strip(),
            wave_id=str(args.wave_id).strip(),
            input_path=staging_path,
            batch_id=str(args.batch_id).strip(),
            provider=str(args.provider_label).strip(),
            model=str(args.model).strip(),
            allow_partial=True,
        )
        print(f"[ok] no pending jobs -> {import_result['final_count']} records")
        return
    base_url = resolve_base_url(cli_value=str(args.base_url).strip(), base_url_file=str(args.base_url_file).strip())
    if not base_url:
        raise SystemExit("[error] missing base URL; pass --base-url / --base-url-file, set OPENAI_BASE_URL, create ~/.config/opencode/relay_base_url, or configure ~/.config/opencode/opencode.json")
    api_key = resolve_api_key(api_key=str(args.api_key).strip(), api_key_file=str(args.api_key_file).strip())
    if not api_key:
        raise SystemExit("[error] missing API key; pass --api-key / --api-key-file, set OPENAI_API_KEY, create ~/.config/opencode/relay_api_key, or configure ~/.config/opencode/opencode.json")

    failed_jobs = 0
    for index, job in enumerate(jobs, start=1):
        payload = build_responses_payload(
            job,
            model=str(args.model).strip(),
            reasoning_effort=str(args.reasoning_effort).strip(),
        )
        response_text = post_responses_stream(
            base_url=base_url,
            api_key=api_key,
            payload=payload,
            timeout=float(args.timeout),
        )
        try:
            review_object = extract_json_object(response_text)
        except Exception as exc:
            failed_jobs += 1
            append_jsonl(
                error_path,
                {
                    "custom_id": job.get("custom_id"),
                    "target_id": job.get("target_id"),
                    "wave_id": job.get("wave_id"),
                    "batch_id": job.get("batch_id"),
                    "model": str(args.model).strip(),
                    "error": str(exc),
                    "response_text": response_text,
                },
            )
            print(f"[warn] {index}/{len(jobs)} skipped parse failure for {job.get('target_id', '')}")
            if float(args.sleep_seconds) > 0:
                time.sleep(float(args.sleep_seconds))
            continue
        append_jsonl(staging_path, {"custom_id": job["custom_id"], "review": review_object})
        import_result = import_wave_results(
            settings=settings,
            run_id=str(args.run_id).strip(),
            session_id=str(args.session_id).strip(),
            wave_id=str(args.wave_id).strip(),
            input_path=staging_path,
            batch_id=str(args.batch_id).strip(),
            provider=str(args.provider_label).strip(),
            model=str(args.model).strip(),
            allow_partial=True,
        )
        print(f"[ok] {index}/{len(jobs)} imported -> {import_result['final_count']} records")
        if float(args.sleep_seconds) > 0:
            time.sleep(float(args.sleep_seconds))
    if failed_jobs:
        print(f"[warn] failed_jobs={failed_jobs} logged_to={error_path}")


if __name__ == "__main__":
    main()
