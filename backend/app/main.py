from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .routes import (
    graph_router,
    health_router,
    review_sessions_router,
    runs_router,
    visualization_router,
)


settings = get_settings()
settings.runtime_root.mkdir(parents=True, exist_ok=True)
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
settings.static_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Poetry Skill Web API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(health_router)
app.include_router(visualization_router)
app.include_router(graph_router)
app.include_router(runs_router)
app.include_router(review_sessions_router)
