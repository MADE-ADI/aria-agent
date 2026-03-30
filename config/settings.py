"""Agent configuration — loads from ~/.aria/config.yaml with env var overrides."""
import os
import sys

# ── Paths ────────────────────────────────────────────────────────────
ARIA_HOME = os.path.expanduser(os.getenv("ARIA_HOME", "~/.aria"))
ARIA_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Detect layout: new (source in ~/.aria/src/) or dev (source = working dir)
_is_installed = ARIA_SRC.rstrip("/").endswith("/.aria/src")

# User data directories (all live under ~/.aria/)
USER_CONFIG_FILE = os.path.join(ARIA_HOME, "config.yaml")
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
        default_config = """# ══════════════════════════════════════════
#  Aria — Configuration
#  Edit this file to customize your agent
# ══════════════════════════════════════════

# LLM Provider
llm:
  provider: cliproxy
  api_key: ""          # or set LLM_API_KEY env var
  model: claude-sonnet-4-6
  base_url: https://api.openai.com/v1   # change to your provider

# Agent
agent:
  name: Aria
  max_iterations: 10

# Logging
log_level: WARNING     # DEBUG, INFO, WARNING, ERROR
"""
        with open(USER_CONFIG_FILE, "w") as f:
            f.write(default_config)


_ensure_dirs()


def _load_config() -> dict:
    """Load config.yaml, return as nested dict."""
    if not os.path.exists(USER_CONFIG_FILE):
        return {}
    try:
        import yaml
        with open(USER_CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Fallback: simple YAML-like parser for basic key: value
        config = {}
        current_section = None
        try:
            with open(USER_CONFIG_FILE) as f:
                for line in f:
                    line = line.rstrip()
                    if not line or line.lstrip().startswith("#"):
                        continue
                    # Section header (no indent)
                    if not line.startswith(" ") and line.endswith(":"):
                        current_section = line[:-1].strip()
                        config[current_section] = {}
                    elif current_section and ":" in line:
                        key, _, val = line.strip().partition(":")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if val == "":
                            val = None
                        config[current_section][key] = val
        except Exception:
            pass
        return config


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
if isinstance(LOG_LEVEL, str):
    LOG_LEVEL = LOG_LEVEL.upper()
