from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..config import get_settings
from ..constants import ACTIVE_PIPELINE_VERSION


router = APIRouter()
settings = get_settings()


@router.api_route("/", methods=["GET", "HEAD"])
def root() -> FileResponse:
    return FileResponse(settings.static_dir / "index.html")


@router.api_route("/health", methods=["GET", "HEAD"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "pipeline_version": ACTIVE_PIPELINE_VERSION,
    }
