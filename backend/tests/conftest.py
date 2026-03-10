from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app import main as app_main
from app.config import Settings
from app.ingest import ingest_run_artifacts
from app.routes import graph as graph_routes
from app.routes import health as health_routes
from app.routes import reviews as review_routes
from app.routes import runs as runs_routes
from app.routes import visualization as visualization_routes


@pytest.fixture()
def api_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runtime_root = tmp_path / "runtime_workspaces"
    static_dir = tmp_path / "static"
    source_folder = tmp_path / "sample_poems"
    logs_dir = tmp_path / "logs"

    runtime_root.mkdir(parents=True, exist_ok=True)
    static_dir.mkdir(parents=True, exist_ok=True)
    source_folder.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "index.html").write_text("<html><body>ok</body></html>", encoding="utf-8")

    test_settings = Settings(
        project_root=tmp_path,
        db_path=tmp_path / "data" / "skill_web.db",
        runtime_root=runtime_root,
        static_dir=static_dir,
        source_folder=source_folder,
        default_project_id="test-project",
        default_location="us-central1",
        default_model_candidates="model-a,model-b",
        default_max_stage_jump=2,
        brainstorm_script=tmp_path / "brainstorm.py",
        merge_script=tmp_path / "merge.py",
        visualization_script=tmp_path / "viz.py",
    )

    for module in (app_main, graph_routes, health_routes, review_routes, runs_routes, visualization_routes):
        monkeypatch.setattr(module, "settings", test_settings)

    # Shared in-memory SQLite for endpoint calls within one test.
    db_uri = f"file:skillweb-{uuid.uuid4().hex}?mode=memory&cache=shared"
    keeper = sqlite3.connect(db_uri, uri=True, check_same_thread=False)
    keeper.row_factory = sqlite3.Row
    keeper.execute("PRAGMA foreign_keys = ON;")
    schema_sql = (Path(__file__).resolve().parents[1] / "app" / "schema.sql").read_text(
        encoding="utf-8"
    )
    keeper.executescript(schema_sql)
    keeper.commit()

    def _connect(_db_path=None):
        conn = sqlite3.connect(db_uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    monkeypatch.setattr(db_module, "connect", _connect)

    def ingest_mock_run(
        run_id: str,
        nodes: list[dict],
        with_visualization: bool = False,
    ) -> str:
        workspace = runtime_root / f"workspace_{run_id}"
        run_dir = workspace / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "master_skill_web.json").write_text(
            json.dumps(nodes, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if with_visualization:
            viz_dir = run_dir / "visualizations"
            viz_dir.mkdir(parents=True, exist_ok=True)
            (viz_dir / "index.html").write_text(
                f"<html><body>{run_id}</body></html>",
                encoding="utf-8",
            )

        with db_module.db_session() as conn:
            ingest_run_artifacts(
                conn=conn,
                run_id=run_id,
                run_dir=run_dir,
                source_folder=source_folder,
                model_used="test-model",
                iterations=1,
                sample_size=1,
                max_stage_jump=2,
                config={
                    "pipeline_version": "v0.3.1",
                    "mode": "full",
                    "source_folder": str(source_folder),
                },
            )
        return run_id

    client = TestClient(app_main.app)

    try:
        yield {
            "client": client,
            "settings": test_settings,
            "source_folder": source_folder,
            "ingest_mock_run": ingest_mock_run,
        }
    finally:
        client.close()
        keeper.close()
