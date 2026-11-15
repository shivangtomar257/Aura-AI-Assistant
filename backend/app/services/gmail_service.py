"""Gmail integration service supporting OAuth2 REST API and simulation fallback."""

import base64
from datetime import datetime
from email.message import EmailMessage
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from ..config import settings
from ..models.schemas import EmailCreateRequest
from .memory_store import store

GMAIL_SCOPES = "https://www.googleapis.com/auth/gmail.compose https://www.googleapis.com/auth/gmail.readonly"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailService:
    """Manages email drafts and sent messages via Gmail OAuth2 API or local simulation."""

    def is_connected(self) -> bool:
        if not settings.GOOGLE_TOKEN_FILE.exists():
            return False
        try:
            data = json.loads(settings.GOOGLE_TOKEN_FILE.read_text(encoding="utf-8"))
            return bool(data.get("access_token"))
        except Exception:
            return False

    def get_auth_url(self) -> Optional[str]:
        if not settings.GOOGLE_CLIENT_ID:
            return None
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": GMAIL_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be configured.")
        resp = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        token_data = resp.json()
        settings.GOOGLE_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        settings.GOOGLE_TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
        return {"connected": True, "scope": token_data.get("scope", "")}

    def _get_access_token(self) -> Optional[str]:
        if not self.is_connected():
            return None
        token_data = json.loads(settings.GOOGLE_TOKEN_FILE.read_text(encoding="utf-8"))
        return token_data.get("access_token")

    @staticmethod
    def _encode_mime(to_email: str, subject: str, body: str) -> str:
        msg = EmailMessage()
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        return base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    def list_emails(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        emails = store.list_items("emails")
        if status:
            return [e for e in emails if e.get("status") == status]
        return emails

    def create_draft(self, req: EmailCreateRequest) -> Dict[str, Any]:
        provider = "simulation"
        external_id = None

        if not settings.SIMULATION_MODE and self.is_connected():
            token = self._get_access_token()
            raw_msg = self._encode_mime(req.to_email, req.subject, req.body)
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            try:
                if req.status == "sent":
                    r = httpx.post(
                        f"{GMAIL_API_BASE}/messages/send",
                        headers=headers,
                        json={"raw": raw_msg},
                        timeout=15.0,
                    )
                else:
                    r = httpx.post(
                        f"{GMAIL_API_BASE}/drafts",
                        headers=headers,
                        json={"message": {"raw": raw_msg}},
                        timeout=15.0,
                    )
                r.raise_for_status()
                external_id = r.json().get("id")
                provider = "gmail_api"
            except Exception:
                provider = "simulation_fallback"

        record = {
            "to_name": req.to_name,
            "to_email": req.to_email,
            "subject": req.subject,
            "body": req.body,
            "status": req.status,
            "provider": provider,
            "external_id": external_id,
            "created_at": datetime.utcnow().isoformat(),
        }
        return store.add_item("emails", record, prefix="eml")

    def send_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        emails = store.list_items("emails")
        target = next((e for e in emails if e.get("id") == email_id), None)
        if not target:
            return None

        updates: Dict[str, Any] = {
            "status": "sent",
            "sent_at": datetime.utcnow().isoformat(),
        }
        if not settings.SIMULATION_MODE and self.is_connected():
            token = self._get_access_token()
            raw_msg = self._encode_mime(target["to_email"], target["subject"], target["body"])
            try:
                r = httpx.post(
                    f"{GMAIL_API_BASE}/messages/send",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"raw": raw_msg},
                    timeout=15.0,
                )
                r.raise_for_status()
                updates["provider"] = "gmail_api"
                updates["external_id"] = r.json().get("id")
            except Exception:
                updates["provider"] = "simulation_fallback"

        return store.update_item("emails", email_id, updates)

    def delete_email(self, email_id: str) -> bool:
        return store.delete_item("emails", email_id)


gmail_service = GmailService()
