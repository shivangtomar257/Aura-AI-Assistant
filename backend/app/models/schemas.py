"""Pydantic schemas for requests, responses, and domain entities."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    DRAFT_EMAIL = "draft_email"
    SEND_EMAIL = "send_email"
    READ_EMAILS = "read_emails"
    MAKE_CALL = "make_call"
    SCHEDULE_EVENT = "schedule_event"
    LIST_EVENTS = "list_events"
    CREATE_TASK = "create_task"
    LIST_TASKS = "list_tasks"
    COMPLETE_TASK = "complete_task"
    ADD_CONTACT = "add_contact"
    GENERAL_CHAT = "general_chat"


class VoiceCommandRequest(BaseModel):
    transcript: str = Field(..., min_length=1, description="Voice transcript or text instruction")
    confirm_execution: bool = Field(
        default=True,
        description="Whether to execute mutating actions immediately or return preview",
    )


class IntentResult(BaseModel):
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    entities: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""


class EmailCreateRequest(BaseModel):
    to_name: str = ""
    to_email: str
    subject: str
    body: str
    status: str = "draft"  # draft | sent


class EmailRecord(BaseModel):
    id: str
    to_name: str = ""
    to_email: str
    subject: str
    body: str
    status: str = "draft"
    provider: str = "simulation"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class CallCreateRequest(BaseModel):
    contact_name: str
    phone_number: Optional[str] = None
    notes: str = ""


class CallRecord(BaseModel):
    id: str
    contact_name: str
    phone_number: str
    status: str = "initiated"  # initiated | connected | completed | missed
    duration_seconds: int = 0
    notes: str = ""
    provider: str = "simulation"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class CalendarEventCreate(BaseModel):
    title: str
    date: str
    time: str
    duration_minutes: int = 30
    attendees: List[str] = Field(default_factory=list)
    location: str = "Google Meet"


class CalendarEvent(BaseModel):
    id: str
    title: str
    date: str
    time: str
    duration_minutes: int = 30
    attendees: List[str] = Field(default_factory=list)
    location: str = "Google Meet"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class TaskCreateRequest(BaseModel):
    title: str
    priority: str = "medium"  # low | medium | high
    due_date: Optional[str] = None


class TaskItem(BaseModel):
    id: str
    title: str
    priority: str = "medium"
    due_date: Optional[str] = None
    completed: bool = False
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Contact(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    role: str = ""


class ActivityLog(BaseModel):
    id: str
    intent: str
    transcript: str
    summary: str
    status: str = "success"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AssistantResponse(BaseModel):
    reply: str
    speech_text: str
    intent: IntentType
    confidence: float
    action_taken: str
    data: Dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
