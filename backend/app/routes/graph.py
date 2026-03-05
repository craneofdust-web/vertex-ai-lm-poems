from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..config import get_settings
from ..constants import ACTIVE_PIPELINE_VERSION
from ..db import db_session
from ..services import graph_service, run_service


router = APIRouter()
settings = get_settings()


@router.api_route("/graph", methods=["GET", "HEAD"])
def get_graph(run_id: str | None = None, include_weak: bool = False) -> dict:
    with db_session() as conn:
        resolved_run_id = run_service.resolve_run_id(
            conn=conn,
            settings=settings,
            run_id=run_id,
            active_pipeline_version=ACTIVE_PIPELINE_VERSION,
        )
        return graph_service.build_graph_payload(
            conn=conn,
            resolved_run_id=resolved_run_id,
            include_weak=include_weak,
            active_pipeline_version=ACTIVE_PIPELINE_VERSION,
        )


@router.api_route("/node/{node_id}", methods=["GET", "HEAD"])
def get_node(node_id: str, run_id: str | None = None) -> dict:
    with db_session() as conn:
        resolved_run_id = run_service.resolve_run_id(
            conn=conn,
            settings=settings,
            run_id=run_id,
            active_pipeline_version=ACTIVE_PIPELINE_VERSION,
        )
        source_folder = graph_service.resolve_source_folder_for_run(
            conn=conn,
            default_source_folder=settings.source_folder,
            resolved_run_id=resolved_run_id,
        )
        return graph_service.build_node_payload(
            conn=conn,
            resolved_run_id=resolved_run_id,
            node_id=node_id,
            source_folder=source_folder,
        )


@router.api_route("/node/{node_id}/lineage", methods=["GET", "HEAD"])
def get_lineage(node_id: str, run_id: str | None = None) -> dict:
    with db_session() as conn:
        resolved_run_id = run_service.resolve_run_id(
            conn=conn,
            settings=settings,
            run_id=run_id,
            active_pipeline_version=ACTIVE_PIPELINE_VERSION,
        )
        return graph_service.build_lineage_payload(
            conn=conn,
            resolved_run_id=resolved_run_id,
            node_id=node_id,
        )


@router.api_route("/search", methods=["GET", "HEAD"])
def search(q: str = Query(..., min_length=1), run_id: str | None = None, limit: int = 20) -> dict:
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="query cannot be blank")
    with db_session() as conn:
        resolved_run_id = run_service.resolve_run_id(
            conn=conn,
            settings=settings,
            run_id=run_id,
            active_pipeline_version=ACTIVE_PIPELINE_VERSION,
        )
        return graph_service.build_search_payload(
            conn=conn,
            resolved_run_id=resolved_run_id,
            query=q,
            limit=limit,
        )
