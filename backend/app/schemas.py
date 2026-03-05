from __future__ import annotations

from pydantic import BaseModel, Field


class RunRequestBody(BaseModel):
    project_id: str | None = None
    location: str | None = None
    model_candidates: str | None = None
    iterations: int | None = Field(default=None, ge=1, le=200)
    sample_size: int | None = Field(default=None, ge=1, le=1000)
    max_stage_jump: int | None = Field(default=None, ge=1, le=10)
    source_folder: str | None = None
    skip_fill: bool = False
