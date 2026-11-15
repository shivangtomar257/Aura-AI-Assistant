"""FastAPI REST API routes for Aura AI Personal Assistant."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ..config import settings
from ..models.schemas import (
    AssistantResponse,
    CalendarEventCreate,
    CallCreateRequest,
    EmailCreateRequest,
    TaskCreateRequest,
    VoiceCommandRequest,
)
from ..services.calendar_task_service import calendar_task_service
from ..services.call_service import call_service
from ..services.gmail_service import gmail_service
from ..services.intent_router import intent_router
from ..services.memory_store import store
from ..services.tts_service import tts_service

router = APIRouter(prefix="/api/v1", tags=["Assistant"])


class TTSRequest(BaseModel):
    text: str


@router.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok", "service": "aura-ai-assistant"}


@router.get("/auth/google/status")
def google_auth_status() -> Dict[str, Any]:
    return {
        "gmail_connected": gmail_service.is_connected(),
        "simulation_mode": settings.SIMULATION_MODE,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
    }


@router.get("/auth/google/login")
def google_auth_login():
    auth_url = gmail_service.get_auth_url()
    if not auth_url:
        raise HTTPException(
            status_code=400,
            detail="GOOGLE_CLIENT_ID is not configured in environment.",
        )
    return RedirectResponse(url=auth_url)


@router.get("/auth/google/callback")
def google_auth_callback(code: str) -> Dict[str, Any]:
    try:
        return gmail_service.exchange_code_for_token(code)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"OAuth2 token exchange failed: {exc}")


@router.post("/tts")
def synthesize_speech(req: TTSRequest) -> Dict[str, Any]:
    """Synthesize spoken audio via Gemini TTS API with graceful browser fallback."""
    audio_b64, provider = tts_service.synthesize(req.text)
    return {
        "audio_base64": audio_b64,
        "mime_type": "audio/wav" if audio_b64 else None,
        "provider": provider,
    }


@router.post("/command", response_model=AssistantResponse)
def process_voice_command(req: VoiceCommandRequest) -> AssistantResponse:
    """Parse and execute a natural-language voice or text command."""
    return intent_router.execute_command(req.transcript, confirm_execution=req.confirm_execution)


@router.get("/state")
def get_dashboard_state() -> Dict[str, Any]:
    """Return full workspace state for initial UI hydration."""
    return store.get_all()


@router.get("/emails")
def list_emails(status: Optional[str] = None) -> List[Dict[str, Any]]:
    return gmail_service.list_emails(status=status)


@router.post("/emails")
def create_email(req: EmailCreateRequest) -> Dict[str, Any]:
    return gmail_service.create_draft(req)


@router.post("/emails/{email_id}/send")
def send_email(email_id: str) -> Dict[str, Any]:
    updated = gmail_service.send_email(email_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Email draft not found")
    return updated


@router.delete("/emails/{email_id}")
def delete_email(email_id: str) -> Dict[str, bool]:
    if not gmail_service.delete_email(email_id):
        raise HTTPException(status_code=404, detail="Email not found")
    return {"deleted": True}


@router.get("/calls")
def list_calls() -> List[Dict[str, Any]]:
    return call_service.list_calls()


@router.post("/calls")
def place_call(req: CallCreateRequest) -> Dict[str, Any]:
    return call_service.place_call(req)


@router.get("/contacts")
def list_contacts() -> List[Dict[str, Any]]:
    return call_service.list_contacts()


@router.get("/calendar")
def list_events() -> List[Dict[str, Any]]:
    return calendar_task_service.list_events()


@router.post("/calendar")
def create_event(req: CalendarEventCreate) -> Dict[str, Any]:
    return calendar_task_service.create_event(req)


@router.delete("/calendar/{event_id}")
def delete_event(event_id: str) -> Dict[str, bool]:
    if not calendar_task_service.delete_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    return {"deleted": True}


@router.get("/tasks")
def list_tasks() -> List[Dict[str, Any]]:
    return calendar_task_service.list_tasks()


@router.post("/tasks")
def create_task(req: TaskCreateRequest) -> Dict[str, Any]:
    return calendar_task_service.create_task(req)


@router.patch("/tasks/{task_id}/toggle")
def toggle_task(task_id: str) -> Dict[str, Any]:
    updated = calendar_task_service.toggle_task(task_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str) -> Dict[str, bool]:
    if not calendar_task_service.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True}


@router.get("/logs")
def list_logs() -> List[Dict[str, Any]]:
    return store.list_items("logs")
