"""
Session manager — persistent, resumable sessions with unique IDs.
"""
import os
import json
import uuid
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class Session:
    """Represents a single conversation session."""

    def __init__(self, session_id: str, user_id: str = "default", metadata: dict = None):
        self.id = session_id
        self.user_id = user_id
        self.messages: list[dict] = []
        self.created_at = time.time()
        self.updated_at = time.time()
        self.metadata = metadata or {}
        self.active = True

    def add_message(self, role: str, content: str):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        self.updated_at = time.time()

    def get_messages(self, last_n: int = 0) -> list[dict]:
        """Get messages formatted for LLM. last_n=0 means all."""
        msgs = self.messages if last_n == 0 else self.messages[-last_n:]
        return [{"role": m["role"], "content": m["content"]} for m in msgs]

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def summary(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "messages": self.message_count,
            "created": datetime.fromtimestamp(self.created_at).isoformat(),
            "updated": datetime.fromtimestamp(self.updated_at).isoformat(),
            "active": self.active,
            "preview": self.messages[0]["content"][:80] if self.messages else "",
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        s = cls(data["id"], data.get("user_id", "default"), data.get("metadata", {}))
        s.messages = data.get("messages", [])
        s.created_at = data.get("created_at", time.time())
        s.updated_at = data.get("updated_at", time.time())
        s.active = data.get("active", True)
        return s


class SessionManager:
    """Manages multiple sessions with persistence."""

    def __init__(self, sessions_dir: str):
        self.sessions_dir = sessions_dir
        self.sessions: dict[str, Session] = {}
        self.active_session: Session | None = None
        os.makedirs(sessions_dir, exist_ok=True)
        self._load_index()

    def _index_path(self) -> str:
        return os.path.join(self.sessions_dir, "index.json")

    def _session_path(self, session_id: str) -> str:
        return os.path.join(self.sessions_dir, f"{session_id}.json")

    def _load_index(self):
        """Load session index (lightweight — only loads metadata, not full messages)."""
        idx_path = self._index_path()
        if not os.path.exists(idx_path):
            return
        with open(idx_path) as f:
            index = json.load(f)
        for sid in index.get("sessions", []):
            fpath = self._session_path(sid)
            if os.path.exists(fpath):
                with open(fpath) as f:
                    self.sessions[sid] = Session.from_dict(json.load(f))

    def _save_index(self):
        with open(self._index_path(), "w") as f:
            json.dump({
                "sessions": list(self.sessions.keys()),
                "updated": time.time(),
            }, f, indent=2)

    def _save_session(self, session: Session):
        with open(self._session_path(session.id), "w") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)

    def create(self, user_id: str = "default", metadata: dict = None) -> Session:
        """Create a new session."""
        sid = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        session = Session(sid, user_id, metadata)
        self.sessions[sid] = session
        self.active_session = session
        self._save_session(session)
        self._save_index()
        logger.info(f"Created session: {sid}")
        return session

    def resume(self, session_id: str) -> Session | None:
        """Resume an existing session."""
        session = self.sessions.get(session_id)
        if session:
            session.active = True
            self.active_session = session
            logger.info(f"Resumed session: {session_id}")
        return session

    def get_active(self) -> Session | None:
        return self.active_session

    def save_current(self):
        """Save the active session to disk."""
        if self.active_session:
            self._save_session(self.active_session)
            self._save_index()

    def end_session(self):
        """End and save the active session."""
        if self.active_session:
            self.active_session.active = False
            self._save_session(self.active_session)
            self._save_index()
            logger.info(f"Ended session: {self.active_session.id}")
            self.active_session = None

    def list_sessions(self, user_id: str = None, limit: int = 20) -> list[dict]:
        """List sessions, optionally filtered by user."""
        sessions = list(self.sessions.values())
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return [s.summary for s in sessions[:limit]]

    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            fpath = self._session_path(session_id)
            if os.path.exists(fpath):
                os.remove(fpath)
            self._save_index()
            if self.active_session and self.active_session.id == session_id:
                self.active_session = None
            return True
        return False
