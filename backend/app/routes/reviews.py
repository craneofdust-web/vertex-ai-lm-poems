from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..review_sessions import get_review_session, list_review_sessions


router = APIRouter()
settings = get_settings()


@router.api_route("/review-sessions", methods=["GET", "HEAD"])
def review_sessions_index(limit: int = 30, run_id: str | None = None) -> dict:
    return {
        "sessions": list_review_sessions(settings=settings, run_id=run_id, limit=limit),
    }


@router.api_route("/review-sessions/{run_id}/{session_id}", methods=["GET", "HEAD"])
def review_session_detail(run_id: str, session_id: str) -> dict:
    try:
        return get_review_session(settings=settings, run_id=run_id, session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
