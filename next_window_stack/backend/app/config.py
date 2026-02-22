from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    project_root: Path
    db_path: Path
    runtime_root: Path
    static_dir: Path
    source_folder: Path
    default_project_id: str
    default_location: str
    default_model_candidates: str
    default_max_stage_jump: int
    brainstorm_script: Path
    merge_script: Path
    visualization_script: Path


def get_settings() -> Settings:
    root = _project_root()
    source_folder_env = os.getenv("POEMS_SOURCE_FOLDER", "").strip()
    source_folder = (
        Path(source_folder_env).expanduser()
        if source_folder_env
        else root / "sample_poems"
    )

    return Settings(
        project_root=root,
        db_path=root / "next_window_stack" / "data" / "skill_web.db",
        runtime_root=root / "runtime_workspaces",
        static_dir=root / "next_window_stack" / "backend" / "static",
        source_folder=source_folder,
        default_project_id=os.getenv("PROJECT_ID", "your-gcp-project-id"),
        default_location=os.getenv("LOCATION", "us-central1"),
        default_model_candidates=os.getenv(
            "VERTEX_MODEL_CANDIDATES", "gemini-3.1,gemini-3-pro,gemini-2.5-pro"
        ),
        default_max_stage_jump=int(os.getenv("MAX_STAGE_JUMP", "2")),
        brainstorm_script=root / "brainstorm_skill_webs.py",
        merge_script=root / "build_master_and_fill_mounting.py",
        visualization_script=root / "generate_skill_tree_visualizations.py",
    )
