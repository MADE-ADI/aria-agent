"""Task manager skill — simple JSON-based to-do list."""
import json
import os
from datetime import datetime

TASKS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "memory", "tasks.json")


def _load():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE) as f:
            return json.load(f)
    return {"next_id": 1, "tasks": []}


def _save(data):
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def execute(action: str, title: str = "", task_id: int = 0, priority: str = "medium") -> dict:
    """Manage tasks."""
    data = _load()

    if action == "add":
        if not title:
            return {"status": "error", "error": "Title is required"}
        task = {
            "id": data["next_id"],
            "title": title,
            "priority": priority,
            "done": False,
            "created": datetime.now().isoformat(),
        }
        data["tasks"].append(task)
        data["next_id"] += 1
        _save(data)
        return {"status": "ok", "action": "added", "task": task}

    elif action == "list":
        pending = [t for t in data["tasks"] if not t["done"]]
        done = [t for t in data["tasks"] if t["done"]]
        return {"status": "ok", "pending": pending, "done_count": len(done), "total": len(data["tasks"])}

    elif action == "done":
        for t in data["tasks"]:
            if t["id"] == task_id:
                t["done"] = True
                t["completed"] = datetime.now().isoformat()
                _save(data)
                return {"status": "ok", "action": "completed", "task": t}
        return {"status": "error", "error": f"Task {task_id} not found"}

    elif action == "delete":
        before = len(data["tasks"])
        data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
        if len(data["tasks"]) == before:
            return {"status": "error", "error": f"Task {task_id} not found"}
        _save(data)
        return {"status": "ok", "action": "deleted", "task_id": task_id}

    return {"status": "error", "error": f"Unknown action: {action}"}
