"""Application configuration and environment settings."""

import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)


class Settings(BaseSettings):
    """Centralized configuration loaded from environment variables or .env."""

    APP_NAME: str = "Aura AI Personal Assistant"
    APP_VERSION: str = "2.0.0"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    SIMULATION_MODE: bool = os.getenv("SIMULATION_MODE", "true").lower() == "true"

    BASE_DIR: Path = BASE_DIR
    DATA_FILE: Path = Path(
        os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "assistant_state.json"))
    )
    GOOGLE_TOKEN_FILE: Path = Path(
        os.getenv("GOOGLE_TOKEN_PATH", str(BASE_DIR / "data" / "google_token.json"))
    )

    # Optional LLM & Gemini Voice TTS configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_TTS_MODEL: str = os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
    GEMINI_VOICE_NAME: str = os.getenv("GEMINI_VOICE_NAME", "Kore")

    # Optional Gmail OAuth2 configuration
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv(
        "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback"
    )

    # Optional Twilio Voice configuration
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "")

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
