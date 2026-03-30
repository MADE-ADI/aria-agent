"""Agent configuration."""
import os

# LLM Provider — default to cliproxy
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "cliproxy")
LLM_API_KEY = os.getenv("LLM_API_KEY", "xkey")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://173.249.59.209:8317/v1")

# Agent
AGENT_NAME = os.getenv("AGENT_NAME", "Aria")
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory")
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
