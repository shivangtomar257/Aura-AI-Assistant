"""Hybrid AI Intent Router (Gemini API + Conversational Q&A + Short-Term Memory + NLP Fallback)."""

import json
import re
from collections import deque
from datetime import datetime, timedelta
from typing import Deque, Dict, Optional, Tuple

import httpx

from ..config import settings
from ..models.schemas import (
    AssistantResponse,
    CalendarEventCreate,
    CallCreateRequest,
    EmailCreateRequest,
    IntentResult,
    IntentType,
    TaskCreateRequest,
)
from .calendar_task_service import calendar_task_service
from .call_service import call_service
from .gmail_service import gmail_service
from .memory_store import store

GEMINI_ENDPOINT_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class IntentRouter:
    """Parses voice transcripts, executes workspace tools, and answers general questions via Gemini."""

    def __init__(self) -> None:
        self._history: Deque[Dict[str, str]] = deque(maxlen=8)
        self._last_draft_id: Optional[str] = None

    def parse_intent(self, transcript: str) -> IntentResult:
        if settings.GEMINI_API_KEY:
            gemini_result = self._parse_with_gemini(transcript)
            if gemini_result is not None:
                return gemini_result
        return self._parse_with_rules(transcript)

    def _parse_with_gemini(self, transcript: str) -> Optional[IntentResult]:
        today = datetime.now().strftime("%Y-%m-%d")
        recent_ctx = "\n".join(
            f"- User: {h['user']} | Assistant: {h['assistant']}" for h in self._history
        )
        system_prompt = (
            "You are an intent classifier for a Google Assistant-style personal AI assistant. "
            f"Today's date is {today}. "
            "Classify the user transcript into ONE intent from: "
            "draft_email, send_email, read_emails, make_call, schedule_event, "
            "list_events, create_task, list_tasks, general_chat. "
            "Use general_chat for any general knowledge question, conversation, or follow-up question "
            "(e.g., 'What is India?', 'Tell me about space', 'How are you?'). "
            "Use recent conversation context if the user says follow-ups like 'send it'. "
            "Return ONLY a JSON object with keys: intent (string), confidence (float 0..1), "
            "entities (object with relevant fields such as to_name, subject, body, contact_name, "
            "phone_number, title, date YYYY-MM-DD, time HH:MM, priority), and reasoning (string)."
        )
        prompt = f"{system_prompt}\n\nRecent Context:\n{recent_ctx or 'None'}\n\nTranscript: {transcript}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        }
        url = GEMINI_ENDPOINT_TMPL.format(model=settings.GEMINI_MODEL)
        try:
            resp = httpx.post(
                url,
                params={"key": settings.GEMINI_API_KEY},
                json=payload,
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_text)
            return IntentResult(
                intent=IntentType(parsed["intent"]),
                confidence=float(parsed.get("confidence", 0.9)),
                entities=parsed.get("entities", {}),
                reasoning=parsed.get("reasoning", "Classified via Gemini API"),
            )
        except Exception:
            return None

    def _answer_general_with_gemini(self, transcript: str) -> str:
        if not settings.GEMINI_API_KEY:
            return (
                "I'm running in offline mode without a Gemini API key right now, so I can't look up general knowledge yet. "
                "Add your GEMINI_API_KEY in .env to ask me anything—or ask me to draft an email, place a call, or schedule a meeting. "
                "Would you like to try one of those?"
            )

        url = GEMINI_ENDPOINT_TMPL.format(model=settings.GEMINI_MODEL)
        recent_ctx = "\n".join(
            f"User: {h['user']}\nAssistant: {h['assistant']}" for h in self._history
        )
        prompt = (
            "You are Aura, a friendly, intelligent Google Assistant-style personal voice assistant. "
            "Answer the user's question clearly and naturally in 2 to 4 spoken sentences (no markdown bullets or asterisks). "
            "End with a short, natural follow-up question like 'Would you like to know more about that, or is there something else I can help you with?'\n\n"
            f"Recent Conversation:\n{recent_ctx or 'None'}\n\n"
            f"User: {transcript}"
        )
        try:
            resp = httpx.post(
                url,
                params={"key": settings.GEMINI_API_KEY},
                json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
                timeout=12.0,
            )
            resp.raise_for_status()
            answer = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if answer:
                return answer
        except Exception:
            pass

        return (
            "I had a brief hiccup reaching Gemini just now. "
            "Could you repeat that, or would you like me to help with your emails, calls, or calendar?"
        )

    def _generate_action_speech(self, action_summary: str, default_speech: str) -> str:
        if not settings.GEMINI_API_KEY:
            return default_speech
        url = GEMINI_ENDPOINT_TMPL.format(model=settings.GEMINI_MODEL)
        prompt = (
            "You are Aura, a warm, capable Google Assistant-style voice assistant. "
            "Rewrite this action confirmation into 1-2 natural spoken sentences (no markdown, no quotes) "
            "and end by asking if there is anything else you can help with:\n"
            f"Action: {action_summary}"
        )
        try:
            resp = httpx.post(
                url,
                params={"key": settings.GEMINI_API_KEY},
                json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
                timeout=8.0,
            )
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return text or default_speech
        except Exception:
            return default_speech

    def _parse_with_rules(self, transcript: str) -> IntentResult:
        text = transcript.strip()
        lower = text.lower()

        if re.search(r"\b(send it|send that|send the draft|go ahead and send)\b", lower) and self._last_draft_id:
            return IntentResult(
                intent=IntentType.SEND_EMAIL,
                confidence=0.95,
                entities={"use_last_draft": True},
                reasoning="Follow-up command to send the most recent draft.",
            )

        if re.search(r"\b(call|dial|phone|ring)\b", lower):
            target = self._extract_after_keywords(text, ["call", "dial", "phone", "ring"])
            phone_match = re.search(r"(\+?\d[\d\-\s]{7,}\d)", text)
            return IntentResult(
                intent=IntentType.MAKE_CALL,
                confidence=0.94,
                entities={
                    "contact_name": target or "Unknown",
                    "phone_number": phone_match.group(1).strip() if phone_match else None,
                },
                reasoning="Detected outbound voice call command.",
            )

        if re.search(r"\b(draft|write|compose|send)\b.*\b(email|mail|gmail|message)\b", lower) or re.search(
            r"\b(email|gmail)\s+to\b", lower
        ):
            is_send = lower.startswith("send ")
            recipient = self._extract_recipient(text)
            subject, body = self._extract_email_content(text, recipient)
            return IntentResult(
                intent=IntentType.SEND_EMAIL if is_send else IntentType.DRAFT_EMAIL,
                confidence=0.93,
                entities={"to_name": recipient, "subject": subject, "body": body},
                reasoning="Detected email composition/drafting instruction.",
            )

        if re.search(r"\b(check|read|show|list|open)\b.*\b(email|emails|gmail|inbox|drafts)\b", lower):
            return IntentResult(
                intent=IntentType.READ_EMAILS,
                confidence=0.91,
                entities={},
                reasoning="Detected email inbox/drafts retrieval request.",
            )

        if re.search(r"\b(schedule|book|set up|create|add)\b.*\b(meeting|event|call|appointment|sync)\b", lower):
            date_str, time_str = self._extract_datetime(text)
            title = self._extract_meeting_title(text)
            return IntentResult(
                intent=IntentType.SCHEDULE_EVENT,
                confidence=0.90,
                entities={"title": title, "date": date_str, "time": time_str},
                reasoning="Detected calendar event scheduling request.",
            )

        if re.search(r"\b(what|show|list|check)\b.*\b(calendar|schedule|agenda|meetings|events)\b", lower):
            return IntentResult(
                intent=IntentType.LIST_EVENTS,
                confidence=0.90,
                entities={},
                reasoning="Detected calendar agenda lookup.",
            )

        if re.search(r"\b(remind|task|todo|to-do|add reminder|create task)\b", lower):
            priority = "high" if any(w in lower for w in ["urgent", "high", "asap", "important"]) else "medium"
            title = self._extract_task_title(text)
            return IntentResult(
                intent=IntentType.CREATE_TASK,
                confidence=0.89,
                entities={"title": title, "priority": priority},
                reasoning="Detected task or reminder creation.",
            )

        if re.search(r"\b(show|list|what|check)\b.*\b(tasks|todos|to-do|reminders)\b", lower):
            return IntentResult(
                intent=IntentType.LIST_TASKS,
                confidence=0.88,
                entities={},
                reasoning="Detected task list retrieval.",
            )

        return IntentResult(
            intent=IntentType.GENERAL_CHAT,
            confidence=0.85,
            entities={"query": text},
            reasoning="General knowledge or conversational question.",
        )

    def execute_command(self, transcript: str, confirm_execution: bool = True) -> AssistantResponse:
        parsed = self.parse_intent(transcript)
        intent = parsed.intent
        ent = parsed.entities

        if intent == IntentType.MAKE_CALL:
            name = ent.get("contact_name", "Unknown")
            contact = store.find_contact(name)
            resolved_name = contact["name"] if contact else name
            phone_number = ent.get("phone_number") or (contact["phone"] if contact else "Unknown Number")
            if not confirm_execution:
                speech = f"I have {resolved_name} ready on {phone_number}. Should I place the call now?"
                return AssistantResponse(
                    reply=f"Ready to call {resolved_name} ({phone_number}). Please confirm to dial.",
                    speech_text=speech,
                    intent=intent,
                    confidence=parsed.confidence,
                    action_taken="preview_call",
                    data={"contact_name": resolved_name, "phone_number": phone_number, "transcript": transcript},
                    requires_confirmation=True,
                )
            call_rec = call_service.place_call(
                CallCreateRequest(contact_name=resolved_name, phone_number=ent.get("phone_number"))
            )
            default_speech = (
                f"Dialing {call_rec['contact_name']} now. "
                "Let me know if there is anything else you want me to do."
            )
            speech = self._generate_action_speech(f"Placed call to {call_rec['contact_name']}", default_speech)
            self._record_turn(transcript, speech, intent.value, f"Placed call to {call_rec['contact_name']}")
            return AssistantResponse(
                reply=speech,
                speech_text=speech,
                intent=intent,
                confidence=parsed.confidence,
                action_taken="call_placed",
                data={"call": call_rec},
            )

        if intent in (IntentType.DRAFT_EMAIL, IntentType.SEND_EMAIL):
            if ent.get("use_last_draft") and self._last_draft_id:
                existing = next((e for e in gmail_service.list_emails() if e["id"] == self._last_draft_id), None)
                if existing:
                    to_name = existing.get("to_name") or existing["to_email"]
                    to_email = existing["to_email"]
                    subject = existing["subject"]
                    body = existing["body"]
                else:
                    to_name, to_email, subject, body = "Priya Sharma", "priya.sharma@example.com", "Follow-up", ""
            else:
                to_name = ent.get("to_name") or "Recipient"
                contact = store.find_contact(to_name)
                to_email = contact["email"] if contact else f"{to_name.lower().replace(' ', '.')}@example.com"
                to_name = contact["name"] if contact else to_name
                subject = ent.get("subject", "Quick Follow-up")
                body = ent.get("body", "")

            if intent == IntentType.SEND_EMAIL and not confirm_execution:
                speech = f"I have the email to {to_name} ready with the subject {subject}. Should I send it now?"
                return AssistantResponse(
                    reply=f"Ready to send email to {to_name} ({to_email}) with subject \"{subject}\". Please confirm.",
                    speech_text=speech,
                    intent=intent,
                    confidence=parsed.confidence,
                    action_taken="preview_send_email",
                    data={
                        "to_name": to_name,
                        "to_email": to_email,
                        "subject": subject,
                        "body": body,
                        "transcript": transcript,
                    },
                    requires_confirmation=True,
                )

            if ent.get("use_last_draft") and self._last_draft_id and confirm_execution:
                email_rec = gmail_service.send_email(self._last_draft_id) or gmail_service.create_draft(
                    EmailCreateRequest(to_name=to_name, to_email=to_email, subject=subject, body=body, status="sent")
                )
                status = "sent"
            else:
                status = "sent" if (intent == IntentType.SEND_EMAIL and confirm_execution) else "draft"
                email_rec = gmail_service.create_draft(
                    EmailCreateRequest(to_name=to_name, to_email=to_email, subject=subject, body=body, status=status)
                )
                if status == "draft":
                    self._last_draft_id = email_rec["id"]

            verb = "Sent" if status == "sent" else "Drafted"
            default_speech = (
                f"I have {'sent' if status == 'sent' else 'drafted'} that email to {to_name} "
                f"about {email_rec['subject']}. "
                + ("Would you like me to send it, or is there anything else?" if status == "draft" else "Is there anything else you want me to do?")
            )
            speech = self._generate_action_speech(f"{verb} email to {to_name}: {email_rec['subject']}", default_speech)
            self._record_turn(transcript, speech, intent.value, f"{verb} email to {to_name}: {email_rec['subject']}")
            return AssistantResponse(
                reply=speech,
                speech_text=speech,
                intent=intent,
                confidence=parsed.confidence,
                action_taken=f"email_{status}",
                data={"email": email_rec},
            )

        if intent == IntentType.READ_EMAILS:
            emails = gmail_service.list_emails()
            default_speech = f"You have {len(emails)} messages and drafts in your Gmail workspace. Is there anything else you want me to do?"
            speech = self._generate_action_speech(f"Checked Gmail: {len(emails)} items", default_speech)
            self._record_turn(transcript, speech, intent.value, f"Listed {len(emails)} emails/drafts")
            return AssistantResponse(
                reply=speech,
                speech_text=speech,
                intent=intent,
                confidence=parsed.confidence,
                action_taken="emails_listed",
                data={"emails": emails},
            )

        if intent == IntentType.SCHEDULE_EVENT:
            evt = calendar_task_service.create_event(
                CalendarEventCreate(
                    title=ent.get("title", "Scheduled Meeting"),
                    date=ent.get("date", datetime.now().strftime("%Y-%m-%d")),
                    time=ent.get("time", "15:00"),
                )
            )
            default_speech = f"I've scheduled {evt['title']} for {evt['date']} at {evt['time']}. Is there anything else you want me to do?"
            speech = self._generate_action_speech(f"Scheduled {evt['title']} on {evt['date']} at {evt['time']}", default_speech)
            self._record_turn(transcript, speech, intent.value, f"Scheduled '{evt['title']}' on {evt['date']} at {evt['time']}")
            return AssistantResponse(
                reply=speech,
                speech_text=speech,
                intent=intent,
                confidence=parsed.confidence,
                action_taken="event_scheduled",
                data={"event": evt},
            )

        if intent == IntentType.LIST_EVENTS:
            events = calendar_task_service.list_events()
            default_speech = f"You have {len(events)} upcoming events on your calendar. Would you like me to schedule anything else?"
            speech = self._generate_action_speech(f"Listed {len(events)} calendar events", default_speech)
            self._record_turn(transcript, speech, intent.value, f"Retrieved {len(events)} calendar events")
            return AssistantResponse(
                reply=speech,
                speech_text=speech,
                intent=intent,
                confidence=parsed.confidence,
                action_taken="events_listed",
                data={"events": events},
            )

        if intent == IntentType.CREATE_TASK:
            task = calendar_task_service.create_task(
                TaskCreateRequest(
                    title=ent.get("title", transcript),
                    priority=ent.get("priority", "medium"),
                    due_date=datetime.now().strftime("%Y-%m-%d"),
                )
            )
            default_speech = f"I've added {task['title']} to your task list. Is there anything else you want me to do?"
            speech = self._generate_action_speech(f"Created task: {task['title']}", default_speech)
            self._record_turn(transcript, speech, intent.value, f"Created task: {task['title']}")
            return AssistantResponse(
                reply=speech,
                speech_text=speech,
                intent=intent,
                confidence=parsed.confidence,
                action_taken="task_created",
                data={"task": task},
            )

        if intent == IntentType.LIST_TASKS:
            tasks = calendar_task_service.list_tasks()
            open_count = len([t for t in tasks if not t.get("completed")])
            default_speech = f"You currently have {open_count} open tasks. Would you like to add or complete one?"
            speech = self._generate_action_speech(f"Listed {open_count} open tasks", default_speech)
            self._record_turn(transcript, speech, intent.value, f"Listed {len(tasks)} tasks")
            return AssistantResponse(
                reply=speech,
                speech_text=speech,
                intent=intent,
                confidence=parsed.confidence,
                action_taken="tasks_listed",
                data={"tasks": tasks},
            )

        # General Knowledge / Conversational Q&A via Gemini
        answer = self._answer_general_with_gemini(transcript)
        self._record_turn(transcript, answer, intent.value, "Answered general conversation query")
        return AssistantResponse(
            reply=answer,
            speech_text=answer,
            intent=intent,
            confidence=parsed.confidence,
            action_taken="general_response",
            data={},
        )

    def _record_turn(self, transcript: str, speech: str, intent: str, summary: str) -> None:
        self._history.append({"user": transcript, "assistant": speech})
        store.add_item(
            "logs",
            {
                "intent": intent,
                "transcript": transcript,
                "summary": summary,
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
            },
            prefix="log",
        )

    @staticmethod
    def _extract_after_keywords(text: str, keywords: list) -> str:
        for kw in keywords:
            m = re.search(rf"\b{kw}\b\s+(.+)", text, re.IGNORECASE)
            if m:
                candidate = re.split(r"\b(about|regarding|at|on|for)\b", m.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
                return candidate.strip(" .,\"'")
        return ""

    @staticmethod
    def _extract_recipient(text: str) -> str:
        m = re.search(r"\bto\s+([A-Za-z][A-Za-z\s]{1,30}?)(?=\s+(?:about|regarding|saying|with|for|$))", text, re.IGNORECASE)
        if m:
            return m.group(1).strip(" .,\"'")
        m2 = re.search(r"\bto\s+([A-Za-z]+)", text, re.IGNORECASE)
        return m2.group(1).strip() if m2 else "Priya Sharma"

    @staticmethod
    def _extract_email_content(text: str, recipient: str) -> Tuple[str, str]:
        topic_match = re.search(r"\b(?:about|regarding|on)\s+(.+)", text, re.IGNORECASE)
        topic = topic_match.group(1).strip(" .") if topic_match else "Project Update"
        subject = topic[:60].capitalize()
        body = (
            f"Hi {recipient},\n\n"
            f"I wanted to reach out regarding {topic}.\n\n"
            f"Please let me know your thoughts or if you'd like to sync on this.\n\n"
            f"Best regards,\nShivang"
        )
        return subject, body

    @staticmethod
    def _extract_datetime(text: str) -> Tuple[str, str]:
        lower = text.lower()
        date_obj = datetime.now()
        if "tomorrow" in lower:
            date_obj += timedelta(days=1)
        date_str = date_obj.strftime("%Y-%m-%d")

        time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lower)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            ampm = time_match.group(3)
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            return date_str, f"{hour:02d}:{minute:02d}"
        return date_str, "15:00"

    @staticmethod
    def _extract_meeting_title(text: str) -> str:
        m = re.search(r"\b(?:with|about|for)\s+([A-Za-z0-9\s\-]{2,40}?)(?=\s+(?:tomorrow|today|at|on|$))", text, re.IGNORECASE)
        if m:
            return f"Sync: {m.group(1).strip().title()}"
        return "Team Sync"

    @staticmethod
    def _extract_task_title(text: str) -> str:
        cleaned = re.sub(
            r"^(?:remind me to|add a task to|create a task to|add reminder to|task:?)\s*",
            "",
            text.strip(),
            flags=re.IGNORECASE,
        )
        return cleaned.strip(" .") or "Follow up on pending action"


intent_router = IntentRouter()
