from __future__ import annotations
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from typing import Dict
from pathlib import Path

from config import settings



app = FastAPI(title="WordQuiz API")

# === Статика (аудио) ===
# Положи файлы в backend/static/audio/*.ogg | *.mp3
static_dir = Path(settings.AUDIO_OUTPUT_DIR)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

from .config import MODULES_ORDER, MODULES_META
from .modules import get_router_for, list_modules


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/modules")
def list_available_modules():
    return {"modules": list_modules(MODULES_ORDER, MODULES_META)}


# Include routers for each module under /modules/<slug>
for slug in MODULES_ORDER:
    try:
        router = get_router_for(slug)
    except Exception:
        continue
    app.include_router(router, prefix=f"/modules/{slug}")

# Keep legacy endpoints for the first module (nationalities) at root
try:
    legacy_router = get_router_for(MODULES_ORDER[0])
    app.include_router(legacy_router)
except Exception:
    pass

