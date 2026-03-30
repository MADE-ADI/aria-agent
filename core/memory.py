"""
Memory system — short-term (conversation) and long-term (file-based) memory.
"""
import os
import json
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class Memory:
    """Manages agent memory with short-term buffer and long-term file storage."""

    def __init__(self, memory_dir: str, max_short_term: int = 50):
        self.memory_dir = memory_dir
        self.max_short_term = max_short_term
        self.short_term: list[dict] = []
        self.long_term_file = os.path.join(memory_dir, "long_term.json")
        os.makedirs(memory_dir, exist_ok=True)
        self._load_long_term()

    def _load_long_term(self):
        if os.path.exists(self.long_term_file):
            with open(self.long_term_file) as f:
                self.long_term = json.load(f)
        else:
            self.long_term = {"facts": [], "preferences": {}, "history": []}

    def _save_long_term(self):
        with open(self.long_term_file, "w") as f:
            json.dump(self.long_term, f, indent=2, ensure_ascii=False)

    def add_message(self, role: str, content: str):
        """Add to short-term conversation buffer."""
        entry = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        self.short_term.append(entry)
        if len(self.short_term) > self.max_short_term:
            self.short_term = self.short_term[-self.max_short_term:]

    def get_conversation(self, last_n: int = 20) -> list[dict]:
        """Get recent conversation for LLM context."""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.short_term[-last_n:]
        ]

    def remember(self, fact: str):
        """Store a fact in long-term memory."""
        entry = {"fact": fact, "timestamp": datetime.now().isoformat()}
        self.long_term["facts"].append(entry)
        self._save_long_term()
        logger.info(f"Remembered: {fact}")

    def set_preference(self, key: str, value: str):
        self.long_term["preferences"][key] = value
        self._save_long_term()

    def recall(self, query: str, limit: int = 5) -> list[str]:
        """Simple keyword search over long-term facts."""
        query_lower = query.lower()
        matches = []
        for entry in self.long_term["facts"]:
            if query_lower in entry["fact"].lower():
                matches.append(entry["fact"])
        return matches[:limit]

    def save_session(self):
        """Persist conversation to daily log."""
        if not self.short_term:
            return
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.memory_dir, f"session_{date_str}.json")

        existing = []
        if os.path.exists(log_file):
            with open(log_file) as f:
                existing = json.load(f)

        existing.extend(self.short_term)
        with open(log_file, "w") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    def clear_short_term(self):
        self.save_session()
        self.short_term = []
