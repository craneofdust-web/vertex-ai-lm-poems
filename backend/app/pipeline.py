from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .config import Settings


@dataclass
class PipelineRequest:
    mode: str
    project_id: str
    location: str
    model_candidates: str
    max_stage_jump: int
    iterations: int | None = None
    sample_size: int | None = None
    skip_fill: bool = False
    source_folder: Path | None = None


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _run_command(
    command: List[str],
    cwd: Path,
    env: Dict[str, str],
    timeout_seconds: int,
    log_path: Path,
) -> Dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
        shell_line = " ".join(shlex.quote(part) for part in command)
        log_file.write(f"$ {shell_line}\n")
        log_file.flush()
        process = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            text=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            errors="replace",
        )
    return {
        "command": command,
        "returncode": process.returncode,
        "log_path": str(log_path),
    }


def _tail_file(path: Path, lines: int = 40) -> str:
    if not path.exists():
        return ""
    chunk = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    return "\n".join(chunk[-lines:])


def _split_candidates(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _detect_model_from_log(log_path: Path, model_candidates: List[str]) -> str | None:
    if not log_path.exists() or not model_candidates:
        return None
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    # Ignore shell header line: "$ python ..."
    lines = [line for line in lines if not line.startswith("$ ")]
    if not lines:
        return None

    fail_hints = (
        "NotFound",
        "PermissionDenied",
        "InvalidArgument",
        "ResourceExhausted",
        "FailedPrecondition",
        "Error",
        "Exception",
        "failed",
    )
    fail_set: set[str] = set()
    seen_set: set[str] = set()
    for line in lines:
        for candidate in model_candidates:
            if candidate in line:
                seen_set.add(candidate)
                if any(hint in line for hint in fail_hints):
                    fail_set.add(candidate)

    for candidate in model_candidates:
        if candidate in seen_set and candidate not in fail_set:
            return candidate
    return None


def run_generation_pipeline(settings: Settings, request: PipelineRequest) -> Dict[str, Any]:
    if request.mode not in {"smoke", "full"}:
        raise ValueError("mode must be either 'smoke' or 'full'")

    source_folder = request.source_folder or settings.source_folder
    if not source_folder.exists():
        raise FileNotFoundError(f"source folder not found: {source_folder}")

    run_id = f"run_{request.mode}_{_timestamp()}"
    workspace = settings.runtime_root / run_id
    workspace.mkdir(parents=True, exist_ok=True)
    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["PROJECT_ID"] = request.project_id
    env["LOCATION"] = request.location
    env["VERTEX_MODEL_CANDIDATES"] = request.model_candidates
    env["STRICT_VALIDATION"] = "1"
    env["WRITE_MARKDOWN_REPORT"] = "1"
    env["WRITE_MOUNTING_INDEX"] = "1"

    if request.sample_size is not None:
        env["SAMPLE_SIZE"] = str(max(1, int(request.sample_size)))
    if request.iterations is not None:
        iterations = max(1, int(request.iterations))
        env["MIN_ITERATIONS"] = str(iterations)
        env["MAX_ITERATIONS"] = str(iterations)

    if request.mode == "smoke":
        env.setdefault("SAMPLE_SIZE", "20")
        env.setdefault("MIN_ITERATIONS", "2")
        env.setdefault("MAX_ITERATIONS", "2")

    candidate_list = _split_candidates(request.model_candidates)
    request_meta = {
        "run_id": run_id,
        "mode": request.mode,
        "project_id": request.project_id,
        "location": request.location,
        "model_candidates": request.model_candidates,
        "iterations": int(env.get("MIN_ITERATIONS", "0")) or None,
        "sample_size": int(env.get("SAMPLE_SIZE", "0")) or None,
        "max_stage_jump": request.max_stage_jump,
        "source_folder": str(source_folder),
        "skip_fill": bool(request.skip_fill),
    }
    (workspace / "pipeline_request.json").write_text(
        json.dumps(request_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    results: List[Dict[str, Any]] = []

    brainstorm_cmd = [sys.executable, str(settings.brainstorm_script)]
    results.append(
        _run_command(
            brainstorm_cmd,
            cwd=workspace,
            env=env,
            timeout_seconds=10800,
            log_path=logs_dir / "01_brainstorm.log",
        )
    )
    if results[-1]["returncode"] != 0:
        log_path = Path(str(results[-1]["log_path"]))
        raise RuntimeError(
            "brainstorm step failed\n"
            f"log_tail:\n{_tail_file(log_path)}"
        )

    merge_cmd = [
        sys.executable,
        str(settings.merge_script),
        "--workdir",
        str(workspace),
        "--run-label",
        run_id,
        "--source-folder",
        str(source_folder),
        "--project-id",
        request.project_id,
        "--location",
        request.location,
        "--model-candidates",
        request.model_candidates,
    ]
    if request.mode == "smoke" or request.skip_fill:
        merge_cmd.append("--skip-fill")

    results.append(
        _run_command(
            merge_cmd,
            cwd=settings.project_root,
            env=env,
            timeout_seconds=10800,
            log_path=logs_dir / "02_merge_fill.log",
        )
    )
    if results[-1]["returncode"] != 0:
        log_path = Path(str(results[-1]["log_path"]))
        raise RuntimeError(
            "merge/fill step failed\n"
            f"log_tail:\n{_tail_file(log_path)}"
        )

    run_dir = workspace / "runs" / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"run output folder missing: {run_dir}")

    viz_cmd = [
        sys.executable,
        str(settings.visualization_script),
        "--master",
        str(run_dir / "master_skill_web.json"),
        "--out-dir",
        str(run_dir / "visualizations"),
        "--poems-root",
        str(source_folder),
    ]
    results.append(
        _run_command(
            viz_cmd,
            cwd=settings.project_root,
            env=env,
            timeout_seconds=10800,
            log_path=logs_dir / "03_visualize.log",
        )
    )
    if results[-1]["returncode"] != 0:
        log_path = Path(str(results[-1]["log_path"]))
        raise RuntimeError(
            "visualization step failed\n"
            f"log_tail:\n{_tail_file(log_path)}"
        )

    generation_model = _detect_model_from_log(logs_dir / "01_brainstorm.log", candidate_list)
    fill_model = _detect_model_from_log(logs_dir / "02_merge_fill.log", candidate_list)
    resolved_model_used = fill_model or generation_model or (candidate_list[0] if candidate_list else "")

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "workspace": str(workspace),
        "mode": request.mode,
        "project_id": request.project_id,
        "location": request.location,
        "model_candidates": request.model_candidates,
        "iterations": int(env.get("MIN_ITERATIONS", "0")) or None,
        "sample_size": int(env.get("SAMPLE_SIZE", "0")) or None,
        "max_stage_jump": request.max_stage_jump,
        "selected_models": {
            "generation_model": generation_model,
            "fill_model": fill_model,
            "model_used": resolved_model_used,
        },
        "commands": [
            {
                "command": result["command"],
                "returncode": result["returncode"],
                "log_path": result["log_path"],
                "log_tail": _tail_file(Path(str(result["log_path"]))),
            }
            for result in results
        ],
    }
