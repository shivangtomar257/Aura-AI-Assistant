# System Architecture — Aura AI Personal Assistant

## 1. High-Level Overview

Aura follows a modular, layered architecture separating voice/UI presentation, intent classification, domain tool services, and persistent state:

```text
+---------------------------------------------------------------+
|                Browser Frontend (frontend/index.html)         |
|  - Web Speech API (SpeechRecognition + speechSynthesis)       |
|  - Live Audio Waveform & Command Input                        |
|  - Workspace Tabs: Overview, Gmail, Calls, Calendar, Tasks    |
+-------------------------------+-------------------------------+
                                | HTTPS / JSON (REST)
                                v
+---------------------------------------------------------------+
|                FastAPI Application (backend/app/main.py)      |
|  - /api/v1/command  -> IntentRouter.execute_command()         |
|  - /api/v1/emails   -> GmailService                           |
|  - /api/v1/calls    -> CallService                            |
|  - /api/v1/calendar -> CalendarTaskService                    |
|  - /api/v1/tasks    -> CalendarTaskService                    |
+-------------------------------+-------------------------------+
                                |
          +---------------------+---------------------+
          |                                           |
          v                                           v
+-----------------------+                 +-----------------------+
| IntentRouter          |                 | MemoryStore           |
| - NLP / Regex Parser  |                 | - Thread-safe JSON    |
| - Entity Extraction   |                 | - Contacts, Emails,   |
| - LLM Upgrade Hook    |                 |   Calls, Events, Logs |
+-----------------------+                 +-----------------------+
```

## 2. Voice Command Pipeline

1. **Capture (`SpeechRecognition`)**: The user clicks the microphone button (or types a command). The browser captures speech in real time and streams interim/final transcripts into the command bar.
2. **Intent Parsing (`IntentRouter.parse_intent`)**:
   - Classifies the transcript into one of `IntentType` (`draft_email`, `send_email`, `read_emails`, `make_call`, `schedule_event`, `list_events`, `create_task`, `list_tasks`, `general_chat`).
   - Extracts structured entities: recipient name, email subject/body, phone number, relative dates (`today`, `tomorrow`), 12h/24h times, and task priority.
3. **Tool Execution**:
   - Resolves contact names against `MemoryStore.find_contact()`.
   - Executes the corresponding domain service (`GmailService`, `CallService`, `CalendarTaskService`).
   - Appends an audit entry to `logs`.
4. **Spoken Feedback (`speechSynthesis`)**: The backend returns both `reply` (markdown/UI text) and `speech_text` (concise natural spoken response), which the browser reads aloud when voice output is enabled.

## 3. Upgrading from Simulation Mode to Live Providers

Set `SIMULATION_MODE=false` in `.env` and populate:
- **Gmail API**: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and OAuth2 token exchange inside `GmailService.create_draft()`.
- **Twilio Voice**: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` inside `CallService.place_call()`.
- **LLM Function Calling**: `OPENAI_API_KEY` or `GEMINI_API_KEY` inside `IntentRouter.parse_intent()` to replace or augment the deterministic parser with tool-calling LLMs.
