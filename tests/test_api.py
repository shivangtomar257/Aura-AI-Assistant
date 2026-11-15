"""Automated API, General Q&A, Gemini TTS, Confirmation Preview, and Gmail OAuth2 test suite."""

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402
from backend.app.main import app  # noqa: E402

client = TestClient(app)


def test_health_check():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_general_question_with_mocked_gemini():
    classify_resp = MagicMock()
    classify_resp.raise_for_status.return_value = None
    classify_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "intent": "general_chat",
                                    "confidence": 0.96,
                                    "entities": {"query": "What is India?"},
                                    "reasoning": "General knowledge question",
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }
    answer_resp = MagicMock()
    answer_resp.raise_for_status.return_value = None
    answer_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "India is a country in South Asia known for its rich history, diverse culture, and rapidly growing technology sector. Would you like to know more about its history or geography?"
                        }
                    ]
                }
            }
        ]
    }

    orig_key = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = "test-gemini-key"
    try:
        with patch("backend.app.services.intent_router.httpx.post", side_effect=[classify_resp, answer_resp]):
            res = client.post("/api/v1/command", json={"transcript": "What is India?"})
            assert res.status_code == 200
            body = res.json()
            assert body["intent"] == "general_chat"
            assert "South Asia" in body["reply"]
            assert body["speech_text"] == body["reply"]
    finally:
        settings.GEMINI_API_KEY = orig_key


def test_tts_endpoint_fallback_and_mocked_gemini():
    fallback = client.post("/api/v1/tts", json={"text": "Hello"})
    assert fallback.status_code == 200
    assert fallback.json()["provider"] == "browser_fallback"

    mock_tts = MagicMock()
    mock_tts.raise_for_status.return_value = None
    mock_tts.json.return_value = {
        "candidates": [{"content": {"parts": [{"inlineData": {"data": "UklGRg=="}}]}}]
    }
    orig_key = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = "test-gemini-key"
    try:
        with patch("backend.app.services.tts_service.httpx.post", return_value=mock_tts):
            live = client.post("/api/v1/tts", json={"text": "Email sent"})
            assert live.status_code == 200
            assert live.json()["provider"] == "gemini_tts"
            assert live.json()["audio_base64"] == "UklGRg=="
    finally:
        settings.GEMINI_API_KEY = orig_key


def test_google_auth_status_and_unconfigured_login():
    status_res = client.get("/api/v1/auth/google/status")
    assert status_res.status_code == 200
    body = status_res.json()
    assert "gmail_connected" in body
    assert "gemini_configured" in body

    login_res = client.get("/api/v1/auth/google/login", allow_redirects=False)
    assert login_res.status_code == 400


def test_draft_and_followup_send_it():
    draft = client.post(
        "/api/v1/command",
        json={"transcript": "Draft an email to Priya about the FastAPI deployment"},
    )
    assert draft.status_code == 200
    assert draft.json()["action_taken"] == "email_draft"

    followup_preview = client.post(
        "/api/v1/command",
        json={"transcript": "Send it", "confirm_execution": False},
    )
    assert followup_preview.status_code == 200
    assert followup_preview.json()["requires_confirmation"] is True
    assert followup_preview.json()["action_taken"] == "preview_send_email"


def test_confirmation_preview_for_call():
    call_preview = client.post(
        "/api/v1/command",
        json={"transcript": "Call Rahul", "confirm_execution": False},
    )
    assert call_preview.status_code == 200
    cp = call_preview.json()
    assert cp["requires_confirmation"] is True
    assert cp["action_taken"] == "preview_call"
    assert cp["data"]["contact_name"] == "Rahul Verma"


def test_voice_command_schedule_meeting():
    res = client.post(
        "/api/v1/command",
        json={"transcript": "Schedule a meeting with Ananya tomorrow at 4 pm"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "schedule_event"
    assert body["data"]["event"]["time"] == "16:00"


if __name__ == "__main__":
    test_health_check()
    test_general_question_with_mocked_gemini()
    test_tts_endpoint_fallback_and_mocked_gemini()
    test_google_auth_status_and_unconfigured_login()
    test_draft_and_followup_send_it()
    test_confirmation_preview_for_call()
    test_voice_command_schedule_meeting()
    print("All Google Assistant-Mode API, Q&A, TTS & OAuth2 tests passed!")
