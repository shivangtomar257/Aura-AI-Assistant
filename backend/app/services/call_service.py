"""Voice calling and contacts service supporting Twilio API or local simulation."""

from datetime import datetime
from typing import Any, Dict, List

from ..config import settings
from ..models.schemas import CallCreateRequest, Contact
from .memory_store import store


class CallService:
    """Handles contact resolution, outbound calls, and call history."""

    def list_calls(self) -> List[Dict[str, Any]]:
        return store.list_items("calls")

    def list_contacts(self) -> List[Dict[str, Any]]:
        return store.list_items("contacts")

    def add_contact(self, name: str, email: str, phone: str, role: str = "") -> Dict[str, Any]:
        return store.add_item(
            "contacts",
            {"name": name, "email": email, "phone": phone, "role": role},
            prefix="cnt",
        )

    def place_call(self, req: CallCreateRequest) -> Dict[str, Any]:
        contact = store.find_contact(req.contact_name)
        phone_number = req.phone_number or (contact["phone"] if contact else "Unknown Number")
        resolved_name = contact["name"] if contact else req.contact_name

        provider = "simulation"
        status = "connected"
        if not settings.SIMULATION_MODE and settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            # Hook for live Twilio Client: client.calls.create(to=..., from_=..., url=...)
            provider = "twilio"
            status = "initiated"

        record = {
            "contact_name": resolved_name,
            "phone_number": phone_number,
            "status": status,
            "duration_seconds": 0,
            "notes": req.notes or f"Voice-initiated call to {resolved_name}",
            "provider": provider,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return store.add_item("calls", record, prefix="cll")


call_service = CallService()
