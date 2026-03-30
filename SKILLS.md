# SKILLS.md — Aria Agent Skills Reference

## Architecture

```
py-agent/
├── main.py              # Entry point + CLI
├── requirements.txt     # Dependencies
├── config/
│   └── settings.py      # Configuration (env vars)
├── core/
│   ├── agent.py         # Agentic loop (reason → plan → act → observe)
│   ├── llm.py           # LLM client (OpenAI-compatible)
│   ├── memory.py        # Short-term + long-term memory
│   ├── session.py       # Session management (create, resume, persist)
│   └── skills.py        # Skill discovery & registry
├── skills/              # Drop-in skill modules
│   ├── image_creator/   # 🎨 Generate images (Recraft AI + Gemini)
│   ├── web_search/      # 🔍 Search the web
│   ├── file_manager/    # 📁 Read, write, list files
│   ├── shell_exec/      # 💻 Execute shell commands
│   ├── remember/        # 🧠 Store facts in memory
│   ├── task_manager/    # ✅ To-do list management
│   ├── weather/         # 🌤️ Weather forecasts
│   ├── calculator/      # 🧮 Safe math evaluation
│   └── summarize/       # 📝 Summarize text/URL/files
├── sessions/            # Persistent sessions (auto-created)
│   ├── index.json       # Session index
│   └── *.json           # Individual session files
├── output/              # Generated files (images, etc.)
└── memory/              # Persistent storage (auto-created)
    ├── long_term.json   # Facts & preferences
    ├── tasks.json       # Task list
    └── session_*.json   # Daily conversation logs
```

## Session System

Every conversation runs inside a **session** with a unique ID. Sessions persist to disk and can be resumed.

### Session Features
- **Auto-create** — a session starts automatically when the agent runs
- **Persistent** — saved to `sessions/<id>.json` after every message
- **Resumable** — pick up where you left off with `/resume <id>`
- **Multi-user** — sessions are tagged by `user_id`
- **Indexed** — `sessions/index.json` tracks all sessions

### CLI Commands
| Command | Action |
|---|---|
| `/sessions` | List all sessions with message count & preview |
| `/session` | Show current session details |
| `/new` | Start a fresh session |
| `/resume <id>` | Resume a previous session (partial ID match) |
| `/end` | End current session |

### Session Storage
```
sessions/
├── index.json                    # Session index
├── 20260329_180413_dbe187.json   # Full session with messages
└── 20260329_180425_d6ec98.json
```

### Programmatic Usage
```python
from core.session import SessionManager

mgr = SessionManager("./sessions")
session = mgr.create(user_id="made")       # New session
sessions = mgr.list_sessions(limit=10)      # List all
mgr.resume("20260329_180413_dbe187")        # Resume by ID
mgr.save_current()                          # Save to disk
mgr.end_session()                           # End & save
```

---

## How the Agent Works

1. **User Input** → Agent receives the message
2. **System Prompt** → Built dynamically with available skills + recalled memories
3. **LLM Reasoning** → Model decides whether to use a skill or answer directly
4. **Tool Execution** → If LLM outputs `{"tool": "name", "args": {...}}`, the skill runs
5. **Observation** → Skill result fed back to LLM for interpretation
6. **Loop** → Steps 3-5 repeat until LLM gives a final text answer (max 10 iterations)

## Built-in Skills

### 🎨 image_creator
Generate images from text prompts using Recraft AI (RecraftV3), with Gemini fallback.
- **Triggers:** generate image, buat gambar, create image, draw, illustrate, gambarkan, bikin gambar
- **Parameters:**
  - `prompt` (string, required): image description
  - `style` (string, optional): realistic_image (default), digital_illustration, vector_illustration, icon
  - `filename` (string, optional): output filename without extension
- **Output:** saved to `output/<filename>.png`
- **Providers:** Recraft AI (primary) → Gemini (fallback)
- **Example:** `"Generate image of a cyberpunk samurai in rain"`

### 🔍 web_search
Search the web via DuckDuckGo (no API key needed).
- **Triggers:** search, cari, google, find info, look up, what is, siapa, apa itu
- **Parameters:** `query` (string, required)
- **Example:** `"Search for latest Python 3.13 features"`

### 📁 file_manager
Read, write, list, append, and delete files.
- **Triggers:** read file, write file, baca file, tulis file, list files, save to file, create file
- **Parameters:**
  - `action` (string): read, write, list, append, delete
  - `path` (string): file/directory path
  - `content` (string, optional): content for write/append
- **Example:** `"List files in the current directory"`

### 💻 shell_exec
Execute shell commands with timeout and safety checks.
- **Triggers:** run command, execute, jalankan, shell, terminal, bash, command
- **Parameters:**
  - `command` (string): shell command
  - `timeout` (int, optional): timeout in seconds (default 30)
- **Safety:** Blocks known destructive patterns (`rm -rf /`, `mkfs`, etc.)
- **Example:** `"Run pip list to see installed packages"`

### 🧠 remember
Store facts in persistent long-term memory.
- **Triggers:** remember, ingat, catat, note, simpan
- **Parameters:** `fact` (string)
- **Example:** `"Remember that the database password is postgres123"`

### ✅ task_manager
Manage a to-do list with priorities.
- **Triggers:** task, todo, tugas, tambah task, add task, done task, list task
- **Parameters:**
  - `action` (string): add, list, done, delete
  - `title` (string, for add): task title
  - `task_id` (int, for done/delete): task ID
  - `priority` (string, optional): low, medium, high
- **Example:** `"Add task: review PR #42 with high priority"`

### 🌤️ weather
Get current weather and 3-day forecast via wttr.in.
- **Triggers:** weather, cuaca, temperature, suhu, forecast, hujan, rain
- **Parameters:** `location` (string)
- **Example:** `"What's the weather in Denpasar?"`

### 🧮 calculator
Safe mathematical expression evaluator.
- **Triggers:** calculate, hitung, math, berapa, kalkulasi, compute
- **Parameters:** `expression` (string)
- **Supported:** +, -, *, /, **, //, %, sqrt, sin, cos, tan, log, pi, e
- **Example:** `"Calculate sqrt(144) + 2^10"`

### 📝 summarize
Summarize text content from direct input, URL, or file.
- **Triggers:** summarize, ringkas, rangkum, summary, tldr, intisari
- **Parameters:**
  - `text` (string, optional): direct text
  - `url` (string, optional): URL to fetch
  - `file` (string, optional): file path
- **Example:** `"Summarize https://example.com/article"`

## Creating Custom Skills

Each skill is a folder in `skills/` with two files:

### 1. `skill.json` — Metadata
```json
{
  "name": "my_skill",
  "description": "What this skill does",
  "triggers": ["keyword1", "keyword2", "kata kunci"],
  "parameters": {
    "param_name": {
      "type": "string",
      "required": true,
      "description": "What this param is"
    }
  },
  "examples": ["example usage 1", "example usage 2"]
}
```

### 2. `main.py` — Logic
```python
"""My custom skill."""

def execute(param_name: str, optional_param: str = "default") -> dict:
    """
    Execute the skill. Must return a dict.
    The agent feeds this result back to the LLM for interpretation.
    """
    # Your logic here
    result = do_something(param_name)
    return {"status": "ok", "result": result}
```

### Rules
- The `execute()` function is **required** — it's the entry point
- Always return a **dict** with at least `"status"` key
- Keep skills **focused** — one skill, one responsibility
- Use `"triggers"` for keyword matching — supports Indonesian and English
- Handle errors gracefully — return `{"status": "error", "error": "message"}`

### Example: Custom "Email Checker" Skill

```
skills/
└── email_check/
    ├── skill.json
    └── main.py
```

**skill.json:**
```json
{
  "name": "email_check",
  "description": "Check for new unread emails",
  "triggers": ["check email", "cek email", "inbox", "unread"],
  "parameters": {},
  "examples": ["check my email", "any new messages?"]
}
```

**main.py:**
```python
import subprocess

def execute() -> dict:
    result = subprocess.run(
        ["gog", "gmail", "search", "is:unread newer_than:1d", "--max", "5"],
        capture_output=True, text=True
    )
    return {"status": "ok", "emails": result.stdout}
```

Drop the folder in `skills/`, restart the agent — it auto-discovers.

## Configuration

Set via environment variables:

| Variable | Default | Description |
|---|---|---|
| `LLM_API_KEY` | _(required)_ | API key for LLM provider |
| `LLM_MODEL` | `gpt-4o` | Model name |
| `LLM_BASE_URL` | OpenAI default | Custom endpoint (for local LLMs, proxies) |
| `LLM_PROVIDER` | `openai` | Provider hint |
| `AGENT_NAME` | `Aria` | Agent display name |
| `MAX_ITERATIONS` | `10` | Max tool-use loops per request |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Using with local models (Ollama, vLLM, etc.)
```bash
export LLM_API_KEY=dummy
export LLM_BASE_URL=http://localhost:11434
export LLM_MODEL=llama3
python main.py
```

## CLI Commands

| Command | Action |
|---|---|
| `/skills` | List all loaded skills |
| `/memory` | Show recent facts in memory |
| `/clear` | Clear conversation context |
| `/quit` | Save session & exit |

## Quick Start

```bash
cd py-agent
pip install -r requirements.txt
export LLM_API_KEY=sk-your-key-here
python main.py
```
