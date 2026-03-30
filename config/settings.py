"""Agent configuration — loads from ~/.aria/config.yaml with env var overrides."""
import os
import sys

# ── Paths ────────────────────────────────────────────────────────────
ARIA_HOME = os.path.expanduser(os.getenv("ARIA_HOME", "~/.aria"))
ARIA_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Detect layout: new (source in ~/.aria/src/) or dev (source = working dir)
_is_installed = ARIA_SRC.rstrip("/").endswith("/.aria/src")

# User data directories (all live under ~/.aria/)
USER_CONFIG_FILE = os.path.join(ARIA_HOME, "config.json")
USER_SKILLS_DIR = os.path.join(ARIA_HOME, "skills")
USER_MEMORY_DIR = os.path.join(ARIA_HOME, "memory")
USER_SESSIONS_DIR = os.path.join(ARIA_HOME, "sessions")
USER_LOGS_DIR = os.path.join(ARIA_HOME, "logs")

# Built-in skills (shipped with source)
BUILTIN_SKILLS_DIR = os.path.join(ARIA_SRC, "skills")


def _ensure_dirs():
    """Create ~/.aria structure on first run."""
    for d in [ARIA_HOME, USER_SKILLS_DIR, USER_MEMORY_DIR, USER_SESSIONS_DIR, USER_LOGS_DIR]:
        os.makedirs(d, exist_ok=True)

    # Create default config if not exists
    if not os.path.exists(USER_CONFIG_FILE):
        import json
        default_config = {
            "llm": {
                "provider": "openai",
                "api_key": "",
                "model": "gpt-4o",
                "base_url": "https://api.openai.com/v1"
            },
            "agent": {
                "name": "Aria",
                "max_iterations": 10
            },
            "log_level": "WARNING"
        }
        with open(USER_CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=2)


_ensure_dirs()


def _load_config() -> dict:
    """Load config.json, return as nested dict."""
    if not os.path.exists(USER_CONFIG_FILE):
        return {}
    try:
        import json
        with open(USER_CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


_cfg = _load_config()
_llm = _cfg.get("llm", {}) if isinstance(_cfg.get("llm"), dict) else {}
_agent = _cfg.get("agent", {}) if isinstance(_cfg.get("agent"), dict) else {}

# ── Final settings (env vars > config.yaml > defaults) ───────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", _llm.get("provider", "cliproxy"))
LLM_API_KEY = os.getenv("LLM_API_KEY", _llm.get("api_key", "") or "")
LLM_MODEL = os.getenv("LLM_MODEL", _llm.get("model", "claude-sonnet-4-6"))
LLM_BASE_URL = os.getenv("LLM_BASE_URL", _llm.get("base_url", "https://api.openai.com/v1"))

AGENT_NAME = os.getenv("AGENT_NAME", _agent.get("name", "Aria"))
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", _agent.get("max_iterations", "10")))

# These now point to ~/.aria/
MEMORY_DIR = USER_MEMORY_DIR
SKILLS_DIR = USER_SKILLS_DIR
SESSIONS_DIR = USER_SESSIONS_DIR

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", _cfg.get("log_level", "WARNING"))
