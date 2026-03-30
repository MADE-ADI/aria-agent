# Aria — Python AI Agent

Personal AI agent framework with pluggable skills, persistent memory, and agentic reasoning loop.

## Features
- 🔄 **Agentic Loop** — reason → plan → act → observe → repeat
- 🧩 **Drop-in Skills** — add skills by creating a folder with `skill.json` + `main.py`
- 🧠 **Memory** — short-term (conversation) + long-term (facts, preferences)
- 📋 **Task Manager** — built-in to-do list with priorities
- 🔍 **Web Search** — DuckDuckGo (no API key needed)
- 💻 **Shell Access** — execute commands with safety guardrails
- 🌤️ **Weather** — current + 3-day forecast
- 🧮 **Calculator** — safe math evaluation
- 📝 **Summarizer** — summarize text, URLs, or files

## Quick Start

```bash
pip install -r requirements.txt
export LLM_API_KEY=sk-your-key
python main.py
```

## Documentation
See [SKILLS.md](SKILLS.md) for full documentation on architecture, all skills, and how to create custom ones.
