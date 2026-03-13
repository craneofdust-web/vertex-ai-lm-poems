from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings
from app.review_exchange import _normalize_stance, export_wave_prompts, import_wave_results, validate_review_record


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=tmp_path,
        db_path=tmp_path / "data" / "skill_web.db",
        runtime_root=tmp_path / "runtime_workspaces",
        static_dir=tmp_path / "static",
        source_folder=tmp_path / "sample_poems",
        default_project_id="test-project",
        default_location="us-central1",
        default_model_candidates="model-a",
        default_max_stage_jump=2,
        brainstorm_script=tmp_path / "brainstorm.py",
        merge_script=tmp_path / "merge.py",
        visualization_script=tmp_path / "viz.py",
    )


def _prepare_session(tmp_path: Path) -> tuple[Settings, Path]:
    settings = _settings(tmp_path)
    run_dir = settings.runtime_root / "workspace_run_full_demo" / "runs" / "run_full_demo"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "master_skill_web.json").write_text("[]", encoding="utf-8")
    session_dir = run_dir.parent.parent / "literary_salon" / "salon_demo"
    (session_dir / "review_batches").mkdir(parents=True, exist_ok=True)
    (session_dir / "review_batches" / "batch_001.jsonl").write_text(
        json.dumps(
            {
                "target_id": "poem-1.md",
                "source_id": "poem-1.md",
                "title": "Poem One",
                "folder_status": "1 文學記錄",
                "completion_status": "unknown",
                "creation_time_hint": "unknown",
                "creation_time_hint_source": "missing",
                "maturity_bucket": "early_archive",
                "comparison_policy": "compare_with_same_stage_only",
                "review_mode": "early_archive_mode",
                "match_count": 1,
                "matched_nodes": [{"node_id": "n1", "node_name": "Node One"}],
                "author_context_flags": {},
                "text_metrics": {"line_count": 4},
                "full_text": "hello poem",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return settings, session_dir


def test_validate_review_record_normalizes_lists() -> None:
    target = {
        "target_id": "poem-1.md",
        "source_id": "poem-1.md",
        "title": "Poem One",
        "review_mode": "early_archive_mode",
        "maturity_bucket": "early_archive",
        "comparison_policy": "compare_with_same_stage_only",
        "match_count": 1,
        "matched_nodes": [{"node_id": "n1", "node_name": "Node One"}],
    }
    payload = {
        "target_id": "poem-1.md",
        "stance": "support",
        "confidence": 0.83,
        "what_works": "anchored image",
        "what_is_being_tested": ["line pressure"],
        "structural_gaps": [],
        "do_not_judge_harshly": ["draft-stage caution"],
        "anticipated_later_work": ["later civic scale"],
        "rationale": "evidence is sufficient",
    }
    normalized = validate_review_record(target, "craft_pass", "batch_001", payload)
    assert normalized["stance"] == "support"
    assert normalized["confidence"] == 0.83
    assert normalized["what_works"] == ["anchored image"]
    assert normalized["top_nodes"] == ["Node One"]


def test_export_and_import_roundtrip(tmp_path: Path) -> None:
    settings, session_dir = _prepare_session(tmp_path)
    exported = export_wave_prompts(settings, "run_full_demo", "salon_demo", "craft_pass", "batch_001")
    assert exported["job_count"] == 1
    prompt_file = Path(exported["batches"][0]["prompt_file"])
    assert prompt_file.is_file()

    raw_import = session_dir / "incoming.jsonl"
    raw_import.write_text(
        json.dumps(
            {
                "custom_id": "craft_pass:batch_001:poem-1.md",
                "review": {
                    "target_id": "poem-1.md",
                    "stance": "revise",
                    "confidence": 0.61,
                    "what_works": ["clear seed image"],
                    "what_is_being_tested": ["voice stability"],
                    "structural_gaps": ["ending is still loose"],
                    "do_not_judge_harshly": ["early archive only"],
                    "anticipated_later_work": ["could become larger sequence"],
                    "rationale": "needs another pass",
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    imported = import_wave_results(
        settings=settings,
        run_id="run_full_demo",
        session_id="salon_demo",
        wave_id="craft_pass",
        input_path=raw_import,
        batch_id="batch_001",
        allow_partial=False,
    )
    assert imported["imported_count"] == 1
    out_path = Path(imported["output_path"])
    rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[0]["target_id"] == "poem-1.md"
    assert rows[0]["stance"] == "revise"


def test_export_wave_prompts_rejects_unknown_batch(tmp_path: Path) -> None:
    settings, _ = _prepare_session(tmp_path)
    try:
        export_wave_prompts(settings, "run_full_demo", "salon_demo", "craft_pass", "batch_999")
    except ValueError as exc:
        assert str(exc) == "batch_id not found: batch_999"
    else:
        raise AssertionError("expected ValueError for unknown batch_id")


def test_normalize_stance_maps_positive_aliases() -> None:
    assert _normalize_stance("qualified_positive") == "support"
    assert _normalize_stance("positive_with_reservations") == "support"
    assert _normalize_stance("retain and develop") == "revise"
