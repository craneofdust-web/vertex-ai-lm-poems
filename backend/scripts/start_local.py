from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent


@dataclass(frozen=True)
class PythonCandidate:
    label: str
    path: Path


def _is_windows() -> bool:
    return os.name == "nt"


def _dedupe(candidates: list[PythonCandidate]) -> list[PythonCandidate]:
    out: list[PythonCandidate] = []
    seen: set[str] = set()
    for item in candidates:
        key = str(item.path.absolute())
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _discover_candidates() -> list[PythonCandidate]:
    candidates: list[PythonCandidate] = []

    current = Path(sys.executable)
    candidates.append(PythonCandidate("current", current))

    local_venv = BACKEND_ROOT / ".venv"
    for name in ("python3", "python"):
        entry = local_venv / ("Scripts" if _is_windows() else "bin") / name
        if _is_windows():
            entry = entry.with_suffix(".exe")
        if entry.exists():
            candidates.append(PythonCandidate(f"local .venv:{name}", entry))

    base_prefix = Path(sys.base_prefix)
    base_python = (
        base_prefix / "python.exe"
        if _is_windows()
        else base_prefix / "bin" / "python3"
    )
    if base_python.exists():
        candidates.append(PythonCandidate("base interpreter", base_python))

    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(PythonCandidate(f"PATH:{name}", Path(found)))

    return _dedupe(candidates)


def _supports_backend(python_path: Path) -> bool:
    probe = (
        "import fastapi,uvicorn;"
        "print('ok',fastapi.__version__,uvicorn.__version__)"
    )
    result = subprocess.run(
        [str(python_path), "-c", probe],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0


def _pick_python() -> PythonCandidate | None:
    for candidate in _discover_candidates():
        if _supports_backend(candidate.path):
            return candidate
    return None


def _run(cmd: list[str], cwd: Path) -> int:
    try:
        process = subprocess.run(cmd, cwd=str(cwd))
    except KeyboardInterrupt:
        return 130
    return int(process.returncode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start backend locally with automatic Python fallback."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--skip-init-db", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    chosen = _pick_python()
    if not chosen:
        print("[error] Could not find a Python with both fastapi and uvicorn installed.")
        print("[hint] Run from backend directory:")
        if _is_windows():
            print("  py -3 -m venv --system-site-packages .venv")
            print("  .\\.venv\\Scripts\\Activate.ps1")
            print("  python -m pip install -r requirements.txt")
        else:
            print("  python3 -m venv --system-site-packages .venv")
            print("  source .venv/bin/activate")
            print("  python3 -m pip install -r requirements.txt")
        print(
            "[hint] If pip shows SSL hostname mismatch for pypi.org, fix network/proxy certificate first."
        )
        return 1

    python_path = chosen.path
    print(f"[ok] Using Python ({chosen.label}): {python_path}")

    if not args.skip_init_db:
        rc = _run([str(python_path), "scripts/init_db.py"], BACKEND_ROOT)
        if rc != 0:
            return rc

    uvicorn_cmd = [
        str(python_path),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.reload:
        uvicorn_cmd.append("--reload")
    return _run(uvicorn_cmd, BACKEND_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
