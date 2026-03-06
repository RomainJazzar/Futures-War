"""
Futures War — MVP Phase 1 : Speech-to-Image
Point d'entrée FastAPI.
"""

import logging
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from models.schemas import HealthResponse
from routers.pipeline import router as pipeline_router

# ── Logging ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("futures-war")

# ── App ──────────────────────────────────────────
app = FastAPI(
    title="Futures War — Speech-to-Image",
    description=(
        "API de génération d'images du futur de Marseille. "
        "Pipeline : voix/texte → transcription → enrichissement prompt → image IA."
    ),
    version="0.1.0",
)

# CORS — utile si le frontend est servi séparément pendant le dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────
app.include_router(pipeline_router)


# ── Health ───────────────────────────────────────
@app.get("/api/health", response_model=HealthResponse, tags=["monitoring"])
async def health():
    """Vérifie que le serveur GPU est joignable."""
    gpu_ok = False
    gpu_stats = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.GPU_URL}/api/system-stats",
                headers={"Authorization": f"Bearer {settings.GPU_TOKEN}"},
            )
            if resp.status_code == 200:
                gpu_ok = True
                gpu_stats = resp.json()
    except Exception:
        pass

    return HealthResponse(
        status="ok" if gpu_ok else "degraded",
        gpu_server_reachable=gpu_ok,
        gpu_stats=gpu_stats,
    )


# ── Static files (frontend) ─────────────────────
# Monté EN DERNIER pour ne pas intercepter /api/* et /docs
# Docker → /app/static exists; local dev → use ../frontend
_static_dir = Path("static")
if not _static_dir.is_dir():
    _static_dir = Path(__file__).resolve().parent.parent / "frontend"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="frontend")
else:
    logger.warning("No static/frontend directory found — frontend will not be served.")
