# API Reference — Aura AI Personal Assistant

Base URL: `http://localhost:8000/api/v1`

## 1. Health Check
- **GET** `/health`
- **Response**: `{"status": "ok", "service": "aura-ai-assistant"}`

## 2. Google Gmail OAuth2 & Provider Status
- **GET** `/auth/google/status` — Returns `{"gmail_connected": bool, "simulation_mode": bool, "gemini_configured": bool}`.
- **GET** `/auth/google/login` — Redirects to Google OAuth2 consent screen (requires `GOOGLE_CLIENT_ID`).
- **GET** `/auth/google/callback?code=...` — Exchanges OAuth2 code for access/refresh tokens and saves `data/google_token.json`.

## 3. Execute Voice / Text Command
- **POST** `/command`
- Uses **Gemini API** (`GEMINI_API_KEY`) when configured, with automatic fallback to the deterministic NLP parser.
- **Body**:
  ```json
  {
    "transcript": "Draft an email to Priya about the FastAPI deployment",
    "confirm_execution": true
  }
  ```

## 4. Workspace State
- **GET** `/state` — Returns all `contacts`, `emails`, `calls`, `events`, `tasks`, and `logs`.

## 5. Emails (Gmail)
- **GET** `/emails?status=draft|sent` — List emails/drafts.
- **POST** `/emails` — Create an email draft or sent record (calls Gmail API when `SIMULATION_MODE=false` and OAuth2 is connected).
- **POST** `/emails/{email_id}/send` — Promote a draft to `sent`.
- **DELETE** `/emails/{email_id}` — Delete an email record.

## 6. Voice Calls & Contacts
- **GET** `/calls` — List call history.
- **POST** `/calls` — Initiate a call (`{"contact_name": "Rahul", "phone_number": null, "notes": ""}`).
- **GET** `/contacts` — List saved contacts.

## 7. Calendar & Tasks
- **GET** `/calendar` — List scheduled events.
- **POST** `/calendar` — Create a new event.
- **DELETE** `/calendar/{event_id}` — Remove an event.
- **GET** `/tasks` — List tasks.
- **POST** `/tasks` — Create a task.
- **PATCH** `/tasks/{task_id}/toggle` — Toggle task completion.
- **DELETE** `/tasks/{task_id}` — Delete a task.

## 8. Activity Logs
- **GET** `/logs` — List recent voice/text command audit logs.
