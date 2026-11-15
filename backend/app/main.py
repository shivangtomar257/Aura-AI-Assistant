"""FastAPI application entrypoint for Aura AI Personal Assistant."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import settings
from .routers.assistant import router as assistant_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Voice-first AI Personal Assistant for Gmail, Calls, Calendar, and Tasks.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assistant_router)

FRONTEND_FILE = Path(__file__).resolve().parent.parent.parent / "frontend" / "index.html"


@app.get("/", include_in_schema=False)
def serve_frontend():
    if FRONTEND_FILE.exists():
        return FileResponse(str(FRONTEND_FILE))
    return {"message": "Aura AI Personal Assistant API is running. Visit /docs for OpenAPI."}
