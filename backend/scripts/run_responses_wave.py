from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error as urlerror

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


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_run_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_error_log(path: Path, payload: dict[str, object]) -> None:
    append_jsonl(path, payload)


def _extract_custom_target_id(raw_custom_id: str) -> str:
    custom_id = str(raw_custom_id or "").strip()
    if custom_id.count(":") >= 2:
        return custom_id.split(":", 2)[2]
    return ""


def _normalize_staging_targets(path: Path) -> None:
    if not path.is_file():
        return
    rows: list[dict[str, object]] = []
    changed = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            continue
        review = payload.get("review")
        if isinstance(review, dict):
            expected = _extract_custom_target_id(str(payload.get("custom_id") or ""))
            if expected:
                current = str(review.get("target_id") or "").strip()
                if current != expected:
                    review["target_id"] = expected
                    changed = True
        rows.append(payload)
    if not changed:
        return
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


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
    parser.add_argument("--max-attempts", type=int, default=6)
    parser.add_argument("--stop-on-429", action="store_true")
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
    run_log_path = session_dir / "run_logs" / f"batch_{str(args.wave_id).strip()}_{Path(str(args.batch_id).strip()).stem}.json"
    output_path = session_dir / "review_waves" / str(args.wave_id).strip() / f"{Path(str(args.batch_id).strip()).stem}.jsonl"
    all_jobs = [
        json.loads(line)
        for line in prompt_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    completed_target_ids = _load_existing_target_ids(output_path)
    jobs = [
        job
        for job in all_jobs
        if str(job.get("target_id") or "").strip() not in completed_target_ids
    ]
    if int(args.max_jobs) > 0:
        jobs = jobs[: int(args.max_jobs)]
    report: dict[str, object] = {
        "run_id": str(args.run_id).strip(),
        "session_id": str(args.session_id).strip(),
        "wave_id": str(args.wave_id).strip(),
        "batch_id": str(args.batch_id).strip(),
        "model": str(args.model).strip(),
        "provider_label": str(args.provider_label).strip(),
        "reasoning_effort": str(args.reasoning_effort).strip(),
        "total_jobs": len(all_jobs),
        "already_completed_jobs": len(all_jobs) - len(jobs),
        "requested_jobs": len(jobs),
        "completed_jobs": 0,
        "failed_jobs": 0,
        "had_429": False,
        "stop_reason": None,
        "manual_action_needed": False,
        "started_at": _iso_now(),
        "finished_at": None,
    }
    if args.dry_run:
        if not jobs:
            print(f"[ok] prompt_file={prompt_file}")
            print("[ok] job_count=0")
            print("[ok] all jobs already completed")
            report["finished_at"] = _iso_now()
            report["stop_reason"] = "no_pending_jobs"
            _write_run_report(run_log_path, report)
            return
        sample = build_responses_payload(jobs[0], model=str(args.model).strip(), reasoning_effort=str(args.reasoning_effort).strip())
        print(f"[ok] prompt_file={prompt_file}")
        print(f"[ok] job_count={len(jobs)}")
        print(f"[ok] sample_model={sample['model']}")
        print(f"[ok] sample_stream={sample['stream']}")
        report["finished_at"] = _iso_now()
        report["stop_reason"] = "dry_run"
        _write_run_report(run_log_path, report)
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
        report["finished_at"] = _iso_now()
        report["stop_reason"] = "no_pending_jobs"
        _write_run_report(run_log_path, report)
        return
    base_url = resolve_base_url(cli_value=str(args.base_url).strip(), base_url_file=str(args.base_url_file).strip())
    if not base_url:
        raise SystemExit("[error] missing base URL; pass --base-url / --base-url-file, set OPENAI_BASE_URL, create ~/.config/opencode/relay_base_url, or configure ~/.config/opencode/opencode.json")
    api_key = resolve_api_key(api_key=str(args.api_key).strip(), api_key_file=str(args.api_key_file).strip())
    if not api_key:
        raise SystemExit("[error] missing API key; pass --api-key / --api-key-file, set OPENAI_API_KEY, create ~/.config/opencode/relay_api_key, or configure ~/.config/opencode/opencode.json")

    failed_jobs = 0
    completed_jobs = 0
    try:
        for index, job in enumerate(jobs, start=1):
            payload = build_responses_payload(
                job,
                model=str(args.model).strip(),
                reasoning_effort=str(args.reasoning_effort).strip(),
            )
            try:
                response_text = post_responses_stream(
                    base_url=base_url,
                    api_key=api_key,
                    payload=payload,
                    timeout=float(args.timeout),
                    max_attempts=max(1, int(args.max_attempts)),
                    stop_on_status=[429] if args.stop_on_429 else None,
                )
            except urlerror.HTTPError as exc:
                status = int(getattr(exc, "code", 0) or 0)
                if status == 429:
                    report["had_429"] = True
                    report["stop_reason"] = "http_429"
                else:
                    report["stop_reason"] = f"http_{status}" if status else "http_error"
                report["manual_action_needed"] = True
                _append_error_log(
                    error_path,
                    {
                        "custom_id": job.get("custom_id"),
                        "target_id": job.get("target_id"),
                        "wave_id": job.get("wave_id"),
                        "batch_id": job.get("batch_id"),
                        "model": str(args.model).strip(),
                        "error_type": "http_error",
                        "status": status,
                        "error": str(exc),
                        "timestamp": _iso_now(),
                    },
                )
                raise SystemExit(2)
            except Exception as exc:
                report["stop_reason"] = "request_error"
                report["manual_action_needed"] = True
                _append_error_log(
                    error_path,
                    {
                        "custom_id": job.get("custom_id"),
                        "target_id": job.get("target_id"),
                        "wave_id": job.get("wave_id"),
                        "batch_id": job.get("batch_id"),
                        "model": str(args.model).strip(),
                        "error_type": "request_error",
                        "error": str(exc),
                        "timestamp": _iso_now(),
                    },
                )
                raise SystemExit(2)
            try:
                review_object = extract_json_object(response_text)
            except Exception as exc:
                failed_jobs += 1
                _append_error_log(
                    error_path,
                    {
                        "custom_id": job.get("custom_id"),
                        "target_id": job.get("target_id"),
                        "wave_id": job.get("wave_id"),
                        "batch_id": job.get("batch_id"),
                        "model": str(args.model).strip(),
                        "error_type": "parse_error",
                        "error": str(exc),
                        "response_text": response_text,
                        "timestamp": _iso_now(),
                    },
                )
                print(f"[warn] {index}/{len(jobs)} skipped parse failure for {job.get('target_id', '')}")
                if float(args.sleep_seconds) > 0:
                    time.sleep(float(args.sleep_seconds))
                continue
            expected_target_id = str(job.get("target_id") or "").strip()
            if expected_target_id:
                review_object["target_id"] = expected_target_id
            append_jsonl(staging_path, {"custom_id": job["custom_id"], "review": review_object})
            _normalize_staging_targets(staging_path)
            try:
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
            except Exception as exc:
                failed_jobs += 1
                report["stop_reason"] = "import_error"
                report["manual_action_needed"] = True
                _append_error_log(
                    error_path,
                    {
                        "custom_id": job.get("custom_id"),
                        "target_id": job.get("target_id"),
                        "wave_id": job.get("wave_id"),
                        "batch_id": job.get("batch_id"),
                        "model": str(args.model).strip(),
                        "error_type": "import_error",
                        "error": str(exc),
                        "timestamp": _iso_now(),
                    },
                )
                raise SystemExit(2)
            completed_jobs += 1
            print(f"[ok] {index}/{len(jobs)} imported -> {import_result['final_count']} records")
            if float(args.sleep_seconds) > 0:
                time.sleep(float(args.sleep_seconds))
    finally:
        report["completed_jobs"] = completed_jobs
        report["failed_jobs"] = failed_jobs
        if failed_jobs:
            report["manual_action_needed"] = True
        report["finished_at"] = _iso_now()
        _write_run_report(run_log_path, report)
    if failed_jobs:
        print(f"[warn] failed_jobs={failed_jobs} logged_to={error_path}")


if __name__ == "__main__":
    main()
