from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from backend.main import app as backend_app


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"


# ============================================================
# APPLICATION
# ============================================================

app = backend_app


# ============================================================
# FRONTEND
# ============================================================

@app.get("/app", include_in_schema=False)
def frontend():
    """
    Serve the Memory Vault frontend.
    """

    if not INDEX_FILE.exists():
        return {
            "status": "error",
            "message": "index.html not found",
        }

    return FileResponse(
        INDEX_FILE,
        media_type="text/html",
    )


# ============================================================
# APPLICATION INFO
# ============================================================

@app.get("/app/status", include_in_schema=False)
def application_status():
    return {
        "application": "RETRO-AI",
        "service": "Context Recovery Engine",
        "status": "running",
        "frontend": (
            "available"
            if INDEX_FILE.exists()
            else "missing"
        ),
        "backend": "connected",
        "reasoning_engine": "connected",
        "n8n": "connected",
    }