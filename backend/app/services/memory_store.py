"""JSON-backed persistent state store for contacts, emails, calls, events, tasks, and logs."""

import json
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings


def _default_state() -> Dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    return {
        "contacts": [
            {
                "id": "cnt_1",
                "name": "Priya Sharma",
                "email": "priya.sharma@example.com",
                "phone": "+91-98110-22334",
                "role": "Engineering Manager",
            },
            {
                "id": "cnt_2",
                "name": "Rahul Verma",
                "email": "rahul.verma@example.com",
                "phone": "+91-98765-43210",
                "role": "Backend Lead",
            },
            {
                "id": "cnt_3",
                "name": "Ananya Gupta",
                "email": "ananya.gupta@example.com",
                "phone": "+91-99100-55667",
                "role": "Product Designer",
            },
            {
                "id": "cnt_4",
                "name": "Vikram Singh",
                "email": "vikram.singh@example.com",
                "phone": "+91-97111-88990",
                "role": "DevOps Engineer",
            },
        ],
        "emails": [
            {
                "id": "eml_1",
                "to_name": "Priya Sharma",
                "to_email": "priya.sharma@example.com",
                "subject": "Weekly Sprint & FastAPI Deployment Update",
                "body": "Hi Priya,\n\nSharing a quick update: the FastAPI service endpoints and Redis caching layer are ready for staging verification.\n\nBest regards,\nShivang",
                "status": "draft",
                "provider": "simulation",
                "created_at": datetime.utcnow().isoformat(),
            }
        ],
        "calls": [
            {
                "id": "cll_1",
                "contact_name": "Rahul Verma",
                "phone_number": "+91-98765-43210",
                "status": "completed",
                "duration_seconds": 185,
                "notes": "Discussed API rate limiting and database indexing.",
                "provider": "simulation",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ],
        "events": [
            {
                "id": "evt_1",
                "title": "Architecture Sync with Priya",
                "date": today,
                "time": "16:00",
                "duration_minutes": 30,
                "attendees": ["priya.sharma@example.com"],
                "location": "Google Meet",
                "created_at": datetime.utcnow().isoformat(),
            },
            {
                "id": "evt_2",
                "title": "UI/UX Review with Ananya",
                "date": tomorrow,
                "time": "11:00",
                "duration_minutes": 45,
                "attendees": ["ananya.gupta@example.com"],
                "location": "Google Meet",
                "created_at": datetime.utcnow().isoformat(),
            },
        ],
        "tasks": [
            {
                "id": "tsk_1",
                "title": "Review FastAPI auth middleware PR",
                "priority": "high",
                "due_date": today,
                "completed": False,
                "created_at": datetime.utcnow().isoformat(),
            },
            {
                "id": "tsk_2",
                "title": "Prepare Docker deployment checklist",
                "priority": "medium",
                "due_date": tomorrow,
                "completed": False,
                "created_at": datetime.utcnow().isoformat(),
            },
        ],
        "logs": [],
    }


class MemoryStore:
    """Thread-safe JSON persistence layer."""

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or settings.DATA_FILE
        self._lock = threading.Lock()
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write(_default_state())

    def _read(self) -> Dict[str, Any]:
        with self._lock:
            if not self.file_path.exists():
                state = _default_state()
                self._write_unlocked(state)
                return state
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)

    def _write_unlocked(self, data: Dict[str, Any]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _write(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self._write_unlocked(data)

    def get_all(self) -> Dict[str, Any]:
        return self._read()

    def list_items(self, collection: str) -> List[Dict[str, Any]]:
        return self._read().get(collection, [])

    def add_item(self, collection: str, item: Dict[str, Any], prefix: str = "itm") -> Dict[str, Any]:
        with self._lock:
            state = json.load(open(self.file_path, "r", encoding="utf-8"))
            if "id" not in item or not item["id"]:
                item["id"] = f"{prefix}_{uuid.uuid4().hex[:8]}"
            state.setdefault(collection, []).insert(0, item)
            self._write_unlocked(state)
            return item

    def update_item(
        self, collection: str, item_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            state = json.load(open(self.file_path, "r", encoding="utf-8"))
            items = state.get(collection, [])
            for idx, item in enumerate(items):
                if item.get("id") == item_id:
                    items[idx].update(updates)
                    self._write_unlocked(state)
                    return items[idx]
            return None

    def delete_item(self, collection: str, item_id: str) -> bool:
        with self._lock:
            state = json.load(open(self.file_path, "r", encoding="utf-8"))
            items = state.get(collection, [])
            filtered = [i for i in items if i.get("id") != item_id]
            if len(filtered) == len(items):
                return False
            state[collection] = filtered
            self._write_unlocked(state)
            return True

    def find_contact(self, query: str) -> Optional[Dict[str, Any]]:
        q = query.strip().lower()
        if not q:
            return None
        contacts = self.list_items("contacts")
        for c in contacts:
            if q == c["name"].lower() or q in c["name"].lower() or q == c["email"].lower():
                return c
        return None


store = MemoryStore()
