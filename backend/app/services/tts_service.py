"""Gemini Text-to-Speech (TTS) service for studio-quality spoken responses."""

from typing import Optional, Tuple
import httpx

from ..config import settings

GEMINI_TTS_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class TTSService:
    """Synthesizes natural speech audio using Gemini TTS API when GEMINI_API_KEY is set."""

    def synthesize(self, text: str) -> Tuple[Optional[str], str]:
        if not settings.GEMINI_API_KEY or not text.strip():
            return None, "browser_fallback"

        url = GEMINI_TTS_TMPL.format(model=settings.GEMINI_TTS_MODEL)
        payload = {
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": settings.GEMINI_VOICE_NAME
                        }
                    }
                },
            },
        }
        try:
            resp = httpx.post(
                url,
                params={"key": settings.GEMINI_API_KEY},
                json=payload,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            parts = data["candidates"][0]["content"]["parts"]
            for part in parts:
                inline = part.get("inlineData")
                if inline and inline.get("data"):
                    return inline["data"], "gemini_tts"
            return None, "browser_fallback"
        except Exception:
            return None, "browser_fallback"


tts_service = TTSService()
