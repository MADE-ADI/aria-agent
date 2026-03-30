#!/usr/bin/env python3
"""
Aria — Python AI Agent
Interactive CLI with agentic loop, skills, sessions, and memory.
"""
import sys
import os
import logging
from config.settings import (
    AGENT_NAME, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL,
    MAX_ITERATIONS, MEMORY_DIR, SKILLS_DIR, LOG_LEVEL,
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
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")

HELP_TEXT = f"""
Aria — Python AI Agent v1.1

Usage:
  aria                     Start interactive session
  aria -e "prompt"         Run single prompt and exit
  aria --logs              Start with logs enabled
  aria --help              Show this help

Interactive Commands:
  /skills          List loaded skills
  /memory          Show remembered facts
  /sessions        List all sessions
  /session         Show current session info
  /new             Start a new session
  /resume <id>     Resume a previous session
  /end             End current session
  /logs on|off     Show/hide agent internal logs
  /clear           Clear conversation context
  /quit            Save & exit

Config:
  LLM_API_KEY      API key (env var or config/settings.py)
  LLM_MODEL        Model name (default: claude-sonnet-4-6)
  LLM_BASE_URL     API endpoint
  AGENT_NAME       Agent display name (default: Aria)

Install dir: {BASE_DIR}
"""


def print_banner(agent_name: str, skills_count: int, session_id: str):
    print(f"""
╔══════════════════════════════════════════╗
║  🤖 {agent_name:^36s} ║
║  Python AI Agent Framework v1.1         ║
║  {skills_count} skills loaded | session: {session_id[:16]:16s}║
╚══════════════════════════════════════════╝

Commands:
  /skills          List loaded skills
  /memory          Show remembered facts
  /sessions        List all sessions
  /session         Show current session info
  /new             Start a new session
  /resume <id>     Resume a previous session
  /end             End current session
  /logs on|off     Show/hide agent internal logs
  /clear           Clear conversation context
  /quit            Save & exit
""")


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
            print("  Usage: aria -e \"what's the weather in Bali?\"")
            sys.exit(1)
        # Suppress python logging in single-prompt mode for clean output
        if not enable_logs:
            logging.disable(logging.CRITICAL)

    if not LLM_API_KEY:
        print("❌ Set LLM_API_KEY environment variable first!")
        print("   export LLM_API_KEY=sk-...")
        sys.exit(1)

    # Init components
    llm = LLMClient(api_key=LLM_API_KEY, model=LLM_MODEL, base_url=LLM_BASE_URL)
    skills = SkillRegistry(SKILLS_DIR)
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

    try:
        while True:
            try:
                active = session_mgr.get_active()
                sid = active.id[:12] if active else "none"
                user_input = input(f"\033[36m[{sid}] {AGENT_NAME}>\033[0m ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            # === Meta commands ===
            if user_input == "/quit":
                session_mgr.save_current()
                memory.save_session()
                print("👋 Session saved. Bye!")
                break

            elif user_input == "/skills":
                print("\n📦 Loaded Skills:")
                for s in skills.list_all():
                    print(f"  • {s['name']}: {s['description']}")
                    print(f"    triggers: {', '.join(s['triggers'])}")
                print()
                continue

            elif user_input == "/memory":
                facts = memory.long_term.get("facts", [])
                print(f"\n🧠 Memory ({len(facts)} facts):")
                for f in facts[-10:]:
                    print(f"  • {f['fact']}")
                print()
                continue

            elif user_input == "/sessions":
                sessions = session_mgr.list_sessions()
                print(f"\n📂 Sessions ({len(sessions)}):")
                for s in sessions:
                    marker = " ← active" if active and s["id"] == active.id else ""
                    print(f"  [{s['id'][:16]}] {s['messages']} msgs | {s['updated']}{marker}")
                    if s["preview"]:
                        print(f"    └─ \"{s['preview'][:60]}...\"")
                print()
                continue

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
                continue

            elif user_input == "/new":
                session_mgr.save_current()
                session = session_mgr.create(user_id="default")
                print(f"\n✨ New session: {session.id}\n")
                continue

            elif user_input.startswith("/resume"):
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print("\n⚠️  Usage: /resume <session_id>")
                    # Show available sessions
                    sessions = session_mgr.list_sessions(limit=5)
                    if sessions:
                        print("  Available:")
                        for s in sessions:
                            print(f"    {s['id'][:16]}  ({s['messages']} msgs)")
                    print()
                    continue
                target_id = parts[1].strip()
                # Allow partial ID match
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
                continue

            elif user_input == "/end":
                if active:
                    print(f"\n🔚 Ended session: {active.id}\n")
                    session_mgr.end_session()
                else:
                    print("\n⚠️  No active session.\n")
                continue

            elif user_input == "/clear":
                memory.clear_short_term()
                print("🧹 Conversation cleared.\n")
                continue

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
