#!/usr/bin/env python3
"""
Aria — Python AI Agent
Interactive CLI with agentic loop, skills, sessions, memory,
and slash-command autocomplete (arrow-key navigable).
"""
import sys
import os
import logging
from config.settings import (
    AGENT_NAME, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL,
    MAX_ITERATIONS, MEMORY_DIR, SKILLS_DIR, SESSIONS_DIR,
    LOG_LEVEL, ARIA_HOME, ARIA_SRC, BUILTIN_SKILLS_DIR,
    USER_CONFIG_FILE,
)
from core.llm import LLMClient
from core.skills import SkillRegistry
from core.memory import Memory
from core.session import SessionManager
from core.agent import Agent

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Slash commands registry ──────────────────────────────────────────
SLASH_COMMANDS = {
    "/skills":   "List loaded skills (builtin + user)",
    "/memory":   "Show remembered facts",
    "/sessions": "List all sessions",
    "/session":  "Show current session info",
    "/new":      "Start a new session",
    "/resume":   "Resume a previous session",
    "/end":      "End current session",
    "/logs":     "Toggle internal logs (on/off)",
    "/clear":    "Clear conversation context",
    "/model":    "Show or change model",
    "/config":   "Show config file path & settings",
    "/path":     "Show all Aria paths",
    "/help":     "Show commands",
    "/quit":     "Save & exit",
}

HELP_TEXT = f"""
Aria — Python AI Agent v1.3

Usage:
  aria                     Start interactive session
  aria -e "prompt"         Run single prompt and exit
  aria --logs              Start with logs enabled
  aria --help              Show this help

Data directory: ~/.aria/
  config.json    — LLM provider, model, agent settings
  skills/        — User custom skills (override built-ins)
  memory/        — Long-term memory storage
  sessions/      — Session history
  logs/          — Agent logs

Interactive Commands (type / for autocomplete):
  /skills          List loaded skills (builtin + user)
  /memory          Show remembered facts
  /sessions        List all sessions
  /session         Show current session info
  /new             Start a new session
  /resume <id>     Resume a previous session
  /end             End current session
  /logs on|off     Show/hide agent internal logs
  /model [name]    Show or change model
  /config          Show config file & current settings
  /path            Show all Aria paths
  /clear           Clear conversation context
  /help            Show commands
  /quit            Save & exit

Config:
  Edit ~/.aria/config.json or use environment variables:
  LLM_API_KEY      API key (env var overrides config)
  LLM_MODEL        Model name
  LLM_BASE_URL     API endpoint
  AGENT_NAME       Agent display name
"""


# ── prompt_toolkit autocomplete ──────────────────────────────────────
def _build_prompt_session(session_mgr):
    """Build a prompt_toolkit PromptSession with slash-command completion."""
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.formatted_text import HTML
        from prompt_toolkit.styles import Style

        class SlashCompleter(Completer):
            def __init__(self, session_mgr_ref):
                self._session_mgr = session_mgr_ref

            def get_completions(self, document, complete_event):
                text = document.text_before_cursor

                # Only trigger on text starting with /
                if not text.startswith("/"):
                    return

                # Match commands
                for cmd, desc in SLASH_COMMANDS.items():
                    if cmd.startswith(text):
                        yield Completion(
                            cmd,
                            start_position=-len(text),
                            display_meta=desc,
                        )

                # Special: /resume shows session IDs
                if text.startswith("/resume "):
                    partial = text[len("/resume "):]
                    try:
                        sessions = self._session_mgr.list_sessions(limit=10)
                        for s in sessions:
                            sid = s["id"]
                            if sid.startswith(partial) or not partial:
                                label = f'{s["messages"]} msgs'
                                yield Completion(
                                    f"/resume {sid}",
                                    start_position=-len(text),
                                    display_meta=label,
                                )
                    except Exception:
                        pass

                # Special: /logs shows on/off
                if text.startswith("/logs "):
                    partial = text[len("/logs "):]
                    for opt in ["on", "off"]:
                        if opt.startswith(partial):
                            yield Completion(
                                f"/logs {opt}",
                                start_position=-len(text),
                                display_meta=f"Turn logs {opt}",
                            )

        style = Style.from_dict({
            "completion-menu":                "bg:#1a1a2e #e0e0e0",
            "completion-menu.completion":      "bg:#1a1a2e #e0e0e0",
            "completion-menu.completion.current": "bg:#16213e #00d4ff bold",
            "completion-menu.meta":            "bg:#1a1a2e #888888",
            "completion-menu.meta.current":    "bg:#16213e #aaaaaa",
            "scrollbar.background":            "bg:#1a1a2e",
            "scrollbar.button":                "bg:#16213e",
        })

        return PromptSession(
            completer=SlashCompleter(session_mgr),
            complete_while_typing=True,
            style=style,
        )
    except ImportError:
        return None


def _fallback_input(prompt_str: str) -> str:
    """Fallback to plain input() if prompt_toolkit isn't available."""
    return input(prompt_str)


def print_banner(agent_name: str, skills_count: int, session_id: str):
    print(f"""
╔══════════════════════════════════════════╗
║  🤖 {agent_name:^36s} ║
║  Python AI Agent Framework v1.3         ║
║  {skills_count} skills loaded | session: {session_id[:16]:16s}║
╚══════════════════════════════════════════╝

  Config:  ~/.aria/config.json
  Skills:  ~/.aria/skills/
  Type / to see commands (arrow keys to navigate)
""")


def handle_command(user_input: str, agent, session_mgr, memory, skills) -> bool:
    """Handle slash commands. Returns True if command was handled, 'quit' to exit."""
    from config.settings import (
        USER_CONFIG_FILE, ARIA_HOME, ARIA_SRC, BUILTIN_SKILLS_DIR,
        SKILLS_DIR, MEMORY_DIR, SESSIONS_DIR, AGENT_NAME, MAX_ITERATIONS,
        LLM_API_KEY,
    )
    active = session_mgr.get_active()

    if user_input == "/quit":
        session_mgr.save_current()
        memory.save_session()
        print("👋 Session saved. Bye!")
        return "quit"

    elif user_input == "/help":
        print("\n📖 Available Commands:")
        for cmd, desc in SLASH_COMMANDS.items():
            print(f"  {cmd:14s}  {desc}")
        print()
        return True

    elif user_input == "/skills":
        print("\n📦 Loaded Skills:")
        for s in skills.list_all():
            badge = "📌" if s.get("source") == "user" else "📦"
            print(f"  {badge} {s['name']}: {s['description']}")
            print(f"     triggers: {', '.join(s['triggers'])}")
        builtin_count = sum(1 for s in skills.list_all() if s.get("source") == "builtin")
        user_count = sum(1 for s in skills.list_all() if s.get("source") == "user")
        print(f"\n  📦 {builtin_count} built-in  |  📌 {user_count} user (~/.aria/skills/)")
        print()
        return True

    elif user_input == "/memory":
        facts = memory.long_term.get("facts", [])
        print(f"\n🧠 Memory ({len(facts)} facts):")
        for f in facts[-10:]:
            print(f"  • {f['fact']}")
        print()
        return True

    elif user_input == "/sessions":
        sessions = session_mgr.list_sessions()
        print(f"\n📂 Sessions ({len(sessions)}):")
        for s in sessions:
            marker = " ← active" if active and s["id"] == active.id else ""
            print(f"  [{s['id'][:16]}] {s['messages']} msgs | {s['updated']}{marker}")
            if s["preview"]:
                print(f'    └─ "{s["preview"][:60]}..."')
        print()
        return True

    elif user_input == "/session":
        if active:
            print(f"\n📌 Current Session:")
            print(f"  ID:       {active.id}")
            print(f"  User:     {active.user_id}")
            print(f"  Messages: {active.message_count}")
            from datetime import datetime
            print(f"  Created:  {datetime.fromtimestamp(active.created_at).isoformat()}")
            print(f"  Updated:  {datetime.fromtimestamp(active.updated_at).isoformat()}")
        else:
            print("\n⚠️  No active session. Use /new to create one.")
        print()
        return True

    elif user_input == "/new":
        session_mgr.save_current()
        session = session_mgr.create(user_id="default")
        print(f"\n✨ New session: {session.id}\n")
        return True

    elif user_input.startswith("/resume"):
        parts = user_input.split(maxsplit=1)
        if len(parts) < 2:
            print("\n⚠️  Usage: /resume <session_id>")
            sessions = session_mgr.list_sessions(limit=5)
            if sessions:
                print("  Available:")
                for s in sessions:
                    print(f"    {s['id'][:16]}  ({s['messages']} msgs)")
            print()
            return True
        target_id = parts[1].strip()
        matched = None
        for sid in session_mgr.sessions:
            if sid.startswith(target_id):
                matched = sid
                break
        if matched:
            session_mgr.save_current()
            resumed = session_mgr.resume(matched)
            print(f"\n🔄 Resumed session: {resumed.id} ({resumed.message_count} messages)\n")
        else:
            print(f"\n❌ Session not found: {target_id}\n")
        return True

    elif user_input == "/end":
        if active:
            print(f"\n🔚 Ended session: {active.id}\n")
            session_mgr.end_session()
        else:
            print("\n⚠️  No active session.\n")
        return True

    elif user_input == "/clear":
        memory.clear_short_term()
        print("🧹 Conversation cleared.\n")
        return True

    elif user_input.startswith("/logs"):
        parts = user_input.split(maxsplit=1)
        if len(parts) < 2:
            status = "ON" if agent.show_logs else "OFF"
            print(f"\n📋 Logs: {status}")
            print("  Usage: /logs on  |  /logs off\n")
        elif parts[1].strip().lower() == "on":
            agent.show_logs = True
            print("\n📋 Logs: ON — you'll see internal agent activity\n")
        elif parts[1].strip().lower() == "off":
            agent.show_logs = False
            print("\n📋 Logs: OFF — clean output only\n")
        else:
            print("\n⚠️  Usage: /logs on  |  /logs off\n")
        return True

    elif user_input.startswith("/model"):
        parts = user_input.split(maxsplit=1)
        if len(parts) < 2:
            print(f"\n🧪 Current model: {agent.llm.model}")
            print(f"  Base URL: {agent.llm.base_url}")
            print("  Usage: /model <model_name> to switch\n")
        else:
            new_model = parts[1].strip()
            agent.llm.model = new_model
            print(f"\n🧪 Model switched to: {new_model}\n")
        return True

    elif user_input == "/config":
        print(f"\n⚙️  Configuration:")
        print(f"  Config file:  {USER_CONFIG_FILE}")
        print(f"  LLM provider: {LLM_API_KEY[:8]}..." if LLM_API_KEY else "  LLM provider: (not set)")
        print(f"  Model:        {agent.llm.model}")
        print(f"  Base URL:     {agent.llm.base_url}")
        print(f"  Agent name:   {AGENT_NAME}")
        print(f"  Max iters:    {MAX_ITERATIONS}")
        print(f"\n  Edit: nano ~/.aria/config.json\n")
        return True

    elif user_input == "/path":
        print(f"\n📁 Aria Paths:")
        print(f"  Home:      {ARIA_HOME}")
        print(f"  Config:    {USER_CONFIG_FILE}")
        print(f"  Skills:    {SKILLS_DIR}  (user)")
        print(f"  Builtin:   {BUILTIN_SKILLS_DIR}")
        print(f"  Memory:    {MEMORY_DIR}")
        print(f"  Sessions:  {SESSIONS_DIR}")
        print(f"  Source:    {ARIA_SRC}")
        print()
        return True

    elif user_input.startswith("/"):
        print(f"\n⚠️  Unknown command: {user_input}")
        print("  Type / to see available commands\n")
        return True

    return False


def main():
    # ---- CLI arguments ----
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(HELP_TEXT)
        sys.exit(0)

    enable_logs = "--logs" in args
    single_prompt = None

    if "-e" in args:
        idx = args.index("-e")
        if idx + 1 < len(args):
            single_prompt = args[idx + 1]
        else:
            print("Error: -e requires a prompt argument")
            print('  Usage: aria -e "what\'s the weather in Bali?"')
            sys.exit(1)
        if not enable_logs:
            logging.disable(logging.CRITICAL)

    if not LLM_API_KEY:
        print("❌ Set LLM_API_KEY environment variable first!")
        print("   export LLM_API_KEY=sk-...")
        sys.exit(1)

    # Init components
    llm = LLMClient(api_key=LLM_API_KEY, model=LLM_MODEL, base_url=LLM_BASE_URL)
    skills = SkillRegistry(SKILLS_DIR, builtin_skills_dir=BUILTIN_SKILLS_DIR)
    memory = Memory(MEMORY_DIR)
    session_mgr = SessionManager(SESSIONS_DIR)
    agent = Agent(
        name=AGENT_NAME,
        llm=llm,
        skills=skills,
        memory=memory,
        session_mgr=session_mgr,
        max_iterations=MAX_ITERATIONS,
    )

    # Auto-create first session
    session = session_mgr.create(user_id="default")

    if enable_logs:
        agent.show_logs = True

    # ---- Single prompt mode: aria -e "prompt" ----
    if single_prompt:
        try:
            response = agent.run(single_prompt)
            print(response)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            session_mgr.save_current()
            llm.close()
        sys.exit(0)

    # ---- Interactive mode ----
    print_banner(AGENT_NAME, len(skills.skills), session.id)

    # Build prompt session with autocomplete
    prompt_session = _build_prompt_session(session_mgr)

    try:
        while True:
            try:
                active = session_mgr.get_active()
                sid = active.id[:12] if active else "none"
                prompt_str = f"\033[36m[{sid}] {AGENT_NAME}>\033[0m "

                if prompt_session:
                    from prompt_toolkit.formatted_text import ANSI
                    user_input = prompt_session.prompt(ANSI(prompt_str)).strip()
                else:
                    user_input = _fallback_input(prompt_str).strip()
            except EOFError:
                break
            except KeyboardInterrupt:
                print()  # newline after ^C
                continue

            if not user_input:
                continue

            # === Handle slash commands ===
            result = handle_command(user_input, agent, session_mgr, memory, skills)
            if result == "quit":
                break
            elif result:
                continue

            # === Agent run ===
            try:
                response = agent.run(user_input)
                print(f"\n\033[33m{response}\033[0m\n")
            except Exception as e:
                logger.error(f"Agent error: {e}", exc_info=True)
                print(f"\n❌ Error: {e}\n")

    except KeyboardInterrupt:
        session_mgr.save_current()
        memory.save_session()
        print("\n👋 Session saved. Bye!")
    finally:
        llm.close()


if __name__ == "__main__":
    main()
