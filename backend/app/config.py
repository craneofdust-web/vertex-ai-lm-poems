from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


ENV_LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if not (candidate / "brainstorm_skill_webs.py").is_file():
            continue
        if (candidate / "backend").is_dir():
            return candidate
    raise RuntimeError(f"unable to detect project root from {here}")


def _normalize_env_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if " #" in value:
        return value.split(" #", 1)[0].rstrip()
    return value


def _load_dotenv_defaults(path: Path) -> None:
    if not path.is_file():
        return
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError:
        return
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ENV_LINE_RE.match(line)
        if not match:
            continue
        key, raw_value = match.groups()
        if key in os.environ:
            continue
        os.environ[key] = _normalize_env_value(raw_value)


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
    _load_dotenv_defaults(root / ".env")
    source_folder_env = os.getenv("POEMS_SOURCE_FOLDER", "").strip()
    source_folder = (
        Path(source_folder_env).expanduser()
        if source_folder_env
        else root / "sample_poems"
    )

    return Settings(
        project_root=root,
        db_path=root / "data" / "skill_web.db",
        runtime_root=root / "runtime_workspaces",
        static_dir=root / "backend" / "static",
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
