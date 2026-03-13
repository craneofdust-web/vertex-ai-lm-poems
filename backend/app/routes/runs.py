from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from ..audit import build_run_audit
from ..config import get_settings
from ..constants import ACTIVE_PIPELINE_VERSION
from ..db import db_session
from ..ingest import ingest_run_artifacts
from ..pipeline import PipelineRequest, run_generation_pipeline
from ..schemas import RunRequestBody
from ..services import run_service


router = APIRouter()
settings = get_settings()


def _run_and_ingest(mode: str, body: RunRequestBody) -> dict:
    project_id = body.project_id or settings.default_project_id
    location = body.location or settings.default_location
    model_candidates = body.model_candidates or settings.default_model_candidates
    max_stage_jump = int(body.max_stage_jump or settings.default_max_stage_jump)
    source_folder = Path(body.source_folder).expanduser() if body.source_folder else settings.source_folder

    pipeline_result = run_generation_pipeline(
        settings,
        PipelineRequest(
            mode=mode,
            project_id=project_id,
            location=location,
            model_candidates=model_candidates,
            max_stage_jump=max_stage_jump,
            iterations=body.iterations,
            sample_size=body.sample_size,
            skip_fill=body.skip_fill,
            source_folder=source_folder,
        ),
    )
    run_id = str(pipeline_result["run_id"])
    run_dir = Path(str(pipeline_result["run_dir"]))

    with db_session() as conn:
        selected_models = pipeline_result.get("selected_models", {}) or {}
        resolved_model_used = str(selected_models.get("model_used") or "").strip()
        if not resolved_model_used:
            resolved_model_used = model_candidates.split(",")[0].strip()
        ingest_result = ingest_run_artifacts(
            conn=conn,
            run_id=run_id,
            run_dir=run_dir,
            source_folder=source_folder,
            model_used=resolved_model_used,
            iterations=pipeline_result.get("iterations"),
            sample_size=pipeline_result.get("sample_size"),
            max_stage_jump=max_stage_jump,
            config={
                "pipeline_version": ACTIVE_PIPELINE_VERSION,
                "mode": mode,
                "project_id": project_id,
                "location": location,
                "model_candidates": model_candidates,
                "source_folder": str(source_folder),
                "selected_models": selected_models,
                "pipeline": pipeline_result.get("commands", []),
            },
        )

    return {
        "pipeline": pipeline_result,
        "ingest": ingest_result,
    }


@router.post("/run/smoke")
def run_smoke(body: RunRequestBody | None = None) -> dict:
    payload = body or RunRequestBody()
    if payload.iterations is None:
        payload.iterations = 2
    if payload.sample_size is None:
        payload.sample_size = 20
    payload.skip_fill = True
    return _run_and_ingest("smoke", payload)


@router.post("/run/full")
def run_full(body: RunRequestBody | None = None) -> dict:
    payload = body or RunRequestBody()
    return _run_and_ingest("full", payload)


@router.api_route("/runs", methods=["GET", "HEAD"])
def list_runs(limit: int = 30) -> dict:
    with db_session() as conn:
        return run_service.list_runs(
            conn=conn,
            settings=settings,
            active_pipeline_version=ACTIVE_PIPELINE_VERSION,
            limit=limit,
        )


@router.api_route("/runs/{run_id}/audit", methods=["GET", "HEAD"])
def run_audit(run_id: str) -> dict:
    with db_session() as conn:
        resolved_run_id = run_service.resolve_run_id(
            conn=conn,
            settings=settings,
            run_id=run_id,
            active_pipeline_version=ACTIVE_PIPELINE_VERSION,
        )
        run_dir = run_service.runtime_run_dir_by_id(settings, resolved_run_id)
        report = build_run_audit(
            conn=conn,
            run_id=resolved_run_id,
            run_dir=run_dir,
            default_source_folder=settings.source_folder,
        )
        report["pipeline_version"] = ACTIVE_PIPELINE_VERSION
        return report
