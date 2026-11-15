"""Calendar events and tasks/reminders management service."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.schemas import CalendarEventCreate, TaskCreateRequest
from .memory_store import store


class CalendarTaskService:
    """Manages calendar schedules and personal to-do tasks."""

    def list_events(self) -> List[Dict[str, Any]]:
        return store.list_items("events")

    def create_event(self, req: CalendarEventCreate) -> Dict[str, Any]:
        record = {
            "title": req.title,
            "date": req.date,
            "time": req.time,
            "duration_minutes": req.duration_minutes,
            "attendees": req.attendees,
            "location": req.location,
            "created_at": datetime.utcnow().isoformat(),
        }
        return store.add_item("events", record, prefix="evt")

    def delete_event(self, event_id: str) -> bool:
        return store.delete_item("events", event_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        return store.list_items("tasks")

    def create_task(self, req: TaskCreateRequest) -> Dict[str, Any]:
        record = {
            "title": req.title,
            "priority": req.priority,
            "due_date": req.due_date,
            "completed": False,
            "created_at": datetime.utcnow().isoformat(),
        }
        return store.add_item("tasks", record, prefix="tsk")

    def toggle_task(self, task_id: str, completed: Optional[bool] = None) -> Optional[Dict[str, Any]]:
        tasks = store.list_items("tasks")
        for t in tasks:
            if t.get("id") == task_id:
                new_val = (not t.get("completed", False)) if completed is None else completed
                return store.update_item("tasks", task_id, {"completed": new_val})
        return None

    def delete_task(self, task_id: str) -> bool:
        return store.delete_item("tasks", task_id)


calendar_task_service = CalendarTaskService()
