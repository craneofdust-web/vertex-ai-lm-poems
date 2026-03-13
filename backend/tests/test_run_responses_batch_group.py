from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "backend" / "scripts" / "run_responses_batch_group.py"
SPEC = importlib.util.spec_from_file_location("run_responses_batch_group", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_session_dir_resolves_workspace_runtime_layout(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_dir = repo_root / "runtime_workspaces" / "workspace_alpha" / "runs" / "run_full_demo"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "master_skill_web.json").write_text("[]", encoding="utf-8")

    session_dir = MODULE._session_dir(repo_root, "run_full_demo", "salon_demo")
    assert session_dir == repo_root / "runtime_workspaces" / "workspace_alpha" / "literary_salon" / "salon_demo"


def test_discover_batches_reads_from_workspace_session(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_dir = repo_root / "runtime_workspaces" / "workspace_alpha" / "runs" / "run_full_demo"
    session_dir = repo_root / "runtime_workspaces" / "workspace_alpha" / "literary_salon" / "salon_demo"
    batches_dir = session_dir / "review_batches"
    batches_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "master_skill_web.json").write_text("[]", encoding="utf-8")
    (batches_dir / "batch_001.jsonl").write_text("{}\n", encoding="utf-8")
    (batches_dir / "batch_002.jsonl").write_text("{}\n", encoding="utf-8")

    assert MODULE.discover_batches(repo_root, "run_full_demo", "salon_demo") == ["batch_001", "batch_002"]
