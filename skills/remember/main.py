"""Memory skill — store and recall facts."""
import json
import os
from datetime import datetime

MEMORY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "memory", "long_term.json")


def _load():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as f:
            return json.load(f)
    return {"facts": [], "preferences": {}, "history": []}


def _save(data):
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def execute(fact: str) -> dict:
    """Store a fact in long-term memory."""
    data = _load()
    entry = {"fact": fact, "timestamp": datetime.now().isoformat()}
    data["facts"].append(entry)
    _save(data)
    return {"status": "ok", "remembered": fact, "total_facts": len(data["facts"])}
