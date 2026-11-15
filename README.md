# Aura — Google-Style AI Personal Assistant

A voice-first, full-stack **AI Personal Assistant Web Application** built with **FastAPI**, **Pydantic**, **Gemini API**, **Web Speech API**, and **Tailwind CSS**. Talk naturally in a continuous two-way conversation to ask general questions, draft or send Gmail messages, place calls, schedule calendar events, and manage tasks.

## Key Features

- **Google Assistant-Style Conversational UI**: Clean dark interface with a 4-color glowing Voice Orb, live non-disappearing speech captions, and a collapsible **Workspace** drawer for Emails, Calls, Calendar, and Tasks.
- **Two-Way Hands-Free Voice Loop**: Tap the Voice Orb once to speak freely—Aura automatically submits your speech when you pause, replies aloud, and resumes listening for follow-up questions.
- **Gemini AI Q&A + Intent Routing**: Uses `gemini-3.5-flash-lite` (with automatic fallback across active Flash models) for general knowledge questions (in English or Hinglish), intent classification, and short-term conversation memory (`"Send it"`).
- **Gemini Text-to-Speech (TTS)**: Optional studio-quality spoken responses via `gemini-3.8-flash-tts` (`POST /api/v1/tts`), with automatic fallback to browser `speechSynthesis`.
- **Gmail OAuth2 Integration**: Authorize your personal Gmail account via `/api/v1/auth/google/login` to create real drafts and send emails, or test safely with `SIMULATION_MODE=true`.
- **Confirmation Preview Modal**: High-impact actions (`send_email`, `make_call`) preview details first and accept voice (`"Yes"` / `"Cancel"`) or click confirmation.

## Project Structure

```text
aura-assistant/
├── backend/
│   └── app/
│       ├── main.py                     # FastAPI entrypoint & static UI serving
│       ├── config.py                   # .env loader & provider configuration
│       ├── models/schemas.py           # Pydantic request/response schemas
│       ├── routers/assistant.py        # /api/v1 REST & OAuth2 endpoints
│       └── services/
│           ├── intent_router.py        # Hybrid Gemini + NLP intent & Q&A router
│           ├── tts_service.py          # Gemini TTS audio synthesis
│           ├── gmail_service.py        # Gmail OAuth2 REST API & simulation
│           ├── call_service.py         # Outbound calls & contacts directory
│           ├── calendar_task_service.py# Calendar events & tasks CRUD
│           └── memory_store.py         # Thread-safe JSON state persistence
├── frontend/index.html                 # Google Assistant-style SPA UI
├── docs/                               # Architecture & API reference docs
├── tests/test_api.py                   # Automated FastAPI TestClient suite
├── .env.example                        # Environment variable template
├── .gitignore                          # Excludes .env, data/, and .venv/
├── requirements.txt                    # Python dependencies
├── Dockerfile                          # Container build definition
└── docker-compose.yml                  # Docker orchestration
```

## Running the Project Locally

1. **Clone or extract the repository**:
   ```bash
   cd aura-assistant
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv .venv
   # macOS / Linux:
   source .venv/bin/activate
   # Windows:
   .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   - To run with zero keys: keep `SIMULATION_MODE=true`.
   - For Gemini Q&A & TTS voice: add `GEMINI_API_KEY=...` (from Google AI Studio).
   - For live Gmail drafts/sending: set `SIMULATION_MODE=false`, `GOOGLE_CLIENT_ID=...`, and `GOOGLE_CLIENT_SECRET=...`.

5. **Start the FastAPI server**:
   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   ```

6. **Open in your browser**:
   - Assistant UI: `http://localhost:8000` (use Chrome or Edge for microphone `SpeechRecognition`)
   - Connect Gmail (if `SIMULATION_MODE=false`): `http://localhost:8000/api/v1/auth/google/login`
   - Interactive API Docs (Swagger): `http://localhost:8000/docs`

## Running Tests & Docker

```bash
# Run automated API tests
python3 tests/test_api.py

# Or run via Docker
docker compose up --build
```
"# Aura-AI-Assistant" 
