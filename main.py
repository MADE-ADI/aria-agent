#!/usr/bin/env python3
"""
Aria — Python AI Agent
Interactive CLI with agentic loop, skills, sessions, memory,
and slash-command autocomplete (arrow-key navigable).
"""
import sys
import os
import logging

# ── Kill ALL logging noise by default ────────────────────────────────
logging.disable(logging.CRITICAL)

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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── ANSI colors ──────────────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    CYAN    = "\033[36m"
    YELLOW  = "\033[33m"
    GREEN   = "\033[32m"
    RED     = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE    = "\033[34m"
    WHITE   = "\033[97m"
    GRAY    = "\033[90m"
    BG_DARK = "\033[48;5;235m"


def dim(text):
    return f"{C.DIM}{text}{C.RESET}"

def cyan(text):
    return f"{C.CYAN}{text}{C.RESET}"

def yellow(text):
    return f"{C.YELLOW}{text}{C.RESET}"

def green(text):
    return f"{C.GREEN}{text}{C.RESET}"

def red(text):
    return f"{C.RED}{text}{C.RESET}"

def bold(text):
    return f"{C.BOLD}{text}{C.RESET}"

def gray(text):
    return f"{C.GRAY}{text}{C.RESET}"


# ── Slash commands registry ──────────────────────────────────────────
SLASH_COMMANDS = {
    "/skills":   "List loaded skills",
    "/memory":   "Show remembered facts",
    "/sessions": "List all sessions",
    "/session":  "Current session info",
    "/new":      "New session",
    "/resume":   "Resume a session",
    "/end":      "End session",
    "/logs":     "Toggle logs (on/off)",
    "/clear":    "Clear context",
    "/model":    "Show/change model",
    "/config":   "Show settings",
    "/path":     "Show paths",
    "/help":     "Show commands",
    "/quit":     "Save & exit",
}

HELP_TEXT = f"""
{C.CYAN}{C.BOLD}Aria{C.RESET} — AI Agent v1.4

{C.BOLD}Usage:{C.RESET}
  aria                     Interactive mode
  aria -e "prompt"         Single prompt
  aria --logs              Start with verbose logs
  aria --help              This help

{C.BOLD}Data:{C.RESET} ~/.aria/
  config.json              Settings
  skills/                  Custom skills
  memory/                  Long-term memory
  sessions/                Session history

{C.BOLD}Config:{C.RESET}
  Edit ~/.aria/config.json or set env vars:
  LLM_API_KEY, LLM_MODEL, LLM_BASE_URL, AGENT_NAME
"""


# ── prompt_toolkit autocomplete ──────────────────────────────────────
def _build_prompt_session(session_mgr):
    """Build a prompt_toolkit PromptSession with slash-command completion."""
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.styles import Style

        class SlashCompleter(Completer):
            def __init__(self, session_mgr_ref):
                self._session_mgr = session_mgr_ref

            def get_completions(self, document, complete_event):
                text = document.text_before_cursor
                if not text.startswith("/"):
                    return

                for cmd, desc in SLASH_COMMANDS.items():
                    if cmd.startswith(text):
                        yield Completion(cmd, start_position=-len(text), display_meta=desc)

                if text.startswith("/resume "):
                    partial = text[len("/resume "):]
                    try:
                        for s in self._session_mgr.list_sessions(limit=10):
                            sid = s["id"]
                            if sid.startswith(partial) or not partial:
                                yield Completion(
                                    f"/resume {sid}", start_position=-len(text),
                                    display_meta=f'{s["messages"]} msgs',
                                )
                    except Exception:
                        pass

                if text.startswith("/logs "):
                    partial = text[len("/logs "):]
                    for opt in ["on", "off"]:
                        if opt.startswith(partial):
                            yield Completion(f"/logs {opt}", start_position=-len(text), display_meta=f"Turn logs {opt}")

        style = Style.from_dict({
            "completion-menu":                   "bg:#1e1e2e #cdd6f4",
            "completion-menu.completion":         "bg:#1e1e2e #cdd6f4",
            "completion-menu.completion.current": "bg:#313244 #89b4fa bold",
            "completion-menu.meta":               "bg:#1e1e2e #6c7086",
            "completion-menu.meta.current":       "bg:#313244 #a6adc8",
            "scrollbar.background":               "bg:#1e1e2e",
            "scrollbar.button":                   "bg:#313244",
        })

        return PromptSession(completer=SlashCompleter(session_mgr), complete_while_typing=True, style=style)
    except ImportError:
        return None


def _dw(text: str) -> int:
    """Display width — accounts for wide chars (emoji, CJK).
    Most terminals render emoji as 2 cells wide."""
    import unicodedata
    w = 0
    i = 0
    chars = list(text)
    while i < len(chars):
        ch = chars[i]
        cp = ord(ch)
        # Skip variation selectors and zero-width joiners
        if cp in (0xFE0E, 0xFE0F, 0x200D):
            i += 1
            continue
        cat = unicodedata.category(ch)
        eaw = unicodedata.east_asian_width(ch)
        if eaw in ("W", "F"):
            w += 2
        elif cp >= 0x1F000:
            # Emoji and symbols above U+1F000 are typically 2 wide
            w += 2
        elif cp >= 0x2600 and cp <= 0x27BF:
            # Misc symbols & dingbats
            w += 2
        elif cat == "Mn":
            # Combining marks — zero width
            pass
        else:
            w += 1
        i += 1
    return w


def _pad(text: str, width: int) -> str:
    """Pad text to exact display width."""
    need = width - _dw(text)
    return text + " " * max(0, need)


BOX_W = 38  # total visible chars between │ and │


def _boxline(text_plain: str, text_ansi: str = None) -> str:
    """Create a box line with exact alignment: │content + padding│"""
    if text_ansi is None:
        text_ansi = text_plain
    pad = BOX_W - _dw(text_plain)
    return f"  {C.CYAN}│{C.RESET}{text_ansi}{' ' * max(0, pad)}{C.CYAN}│{C.RESET}"


def print_banner(agent_name: str, model: str, skills_count: int, session_id: str):
    model_short = model[:34]
    skills_str = f"{skills_count} skills | {session_id[:12]}"
    border = "─" * BOX_W

    print()
    print(f"  {C.CYAN}┌{border}┐{C.RESET}")
    print(_boxline(f"  {agent_name}",       f"  {C.BOLD}{agent_name}{C.RESET}"))
    print(_boxline(f"  {model_short}",      f"  {C.GRAY}{model_short}{C.RESET}"))
    print(_boxline(f"  {skills_str}",       f"  {C.GRAY}{skills_str}{C.RESET}"))
    print(f"  {C.CYAN}└{border}┘{C.RESET}")
    print()
    print(f"  {gray('Type / for commands | /help for details')}")
    print()


def handle_command(user_input: str, agent, session_mgr, memory, skills) -> bool:
    """Handle slash commands. Returns True if handled, 'quit' to exit."""
    from config.settings import (
        USER_CONFIG_FILE, ARIA_HOME, ARIA_SRC, BUILTIN_SKILLS_DIR,
        SKILLS_DIR, MEMORY_DIR, SESSIONS_DIR, AGENT_NAME, MAX_ITERATIONS,
        LLM_API_KEY,
    )
    active = session_mgr.get_active()

    if user_input == "/quit":
        session_mgr.save_current()
        memory.save_session()
        print(f"\n  {gray('Session saved. Goodbye!')} 👋\n")
        return "quit"

    elif user_input == "/help":
        print(f"\n  {bold('Commands:')}")
        for cmd, desc in SLASH_COMMANDS.items():
            print(f"  {cyan(f'{cmd:12s}')}  {desc}")
        print()
        return True

    elif user_input == "/skills":
        all_skills = skills.list_all()
        builtin = [s for s in all_skills if s.get("source") == "builtin"]
        user = [s for s in all_skills if s.get("source") == "user"]

        print(f"\n  {bold('Skills')} {gray(f'({len(all_skills)} total)')}")
        if builtin:
            print(f"\n  {dim('Built-in:')}")
            for s in builtin:
                print(f"    {cyan(s['name']):20s}  {s['description']}")
        if user:
            print(f"\n  {dim('User (~/.aria/skills/):')}")
            for s in user:
                print(f"    {green(s['name']):20s}  {s['description']}")
        if not all_skills:
            print(f"    {gray('No skills loaded')}")
        print()
        return True

    elif user_input == "/memory":
        facts = memory.long_term.get("facts", [])
        print(f"\n  {bold('Memory')} {gray(f'({len(facts)} facts)')}")
        if facts:
            for f in facts[-10:]:
                print(f"    • {f['fact']}")
        else:
            print(f"    {gray('No memories yet')}")
        print()
        return True

    elif user_input == "/sessions":
        sessions = session_mgr.list_sessions()
        print(f"\n  {bold('Sessions')} {gray(f'({len(sessions)} total)')}")
        for s in sessions:
            marker = f" {green('● active')}" if active and s["id"] == active.id else ""
            print(f"    {cyan(s['id'][:16])}  {s['messages']:3d} msgs  {gray(s['updated'])}{marker}")
        if not sessions:
            print(f"    {gray('No sessions')}")
        print()
        return True

    elif user_input == "/session":
        if active:
            from datetime import datetime
            print(f"\n  {bold('Current Session')}")
            print(f"    ID:        {cyan(active.id)}")
            print(f"    Messages:  {active.message_count}")
            print(f"    Created:   {gray(datetime.fromtimestamp(active.created_at).strftime('%Y-%m-%d %H:%M'))}")
            print(f"    Updated:   {gray(datetime.fromtimestamp(active.updated_at).strftime('%Y-%m-%d %H:%M'))}")
        else:
            print(f"\n  {gray('No active session. Use /new')}")
        print()
        return True

    elif user_input == "/new":
        session_mgr.save_current()
        session = session_mgr.create(user_id="default")
        print(f"\n  {green('✓')} New session: {cyan(session.id[:16])}\n")
        return True

    elif user_input.startswith("/resume"):
        parts = user_input.split(maxsplit=1)
        if len(parts) < 2:
            print(f"\n  Usage: {cyan('/resume <session_id>')}")
            sessions = session_mgr.list_sessions(limit=5)
            if sessions:
                for s in sessions:
                    print(f"    {cyan(s['id'][:16])}  ({s['messages']} msgs)")
            print()
            return True
        target_id = parts[1].strip()
        matched = next((sid for sid in session_mgr.sessions if sid.startswith(target_id)), None)
        if matched:
            session_mgr.save_current()
            resumed = session_mgr.resume(matched)
            print(f"\n  {green('✓')} Resumed: {cyan(resumed.id[:16])} ({resumed.message_count} messages)\n")
        else:
            print(f"\n  {red('✗')} Session not found: {target_id}\n")
        return True

    elif user_input == "/end":
        if active:
            print(f"\n  {green('✓')} Ended: {cyan(active.id[:16])}\n")
            session_mgr.end_session()
        else:
            print(f"\n  {gray('No active session')}\n")
        return True

    elif user_input == "/clear":
        memory.clear_short_term()
        print(f"\n  {green('✓')} Context cleared\n")
        return True

    elif user_input.startswith("/logs"):
        parts = user_input.split(maxsplit=1)
        if len(parts) < 2:
            status = green("ON") if agent.show_logs else gray("OFF")
            print(f"\n  Logs: {status}  {gray('(/logs on | /logs off)')}\n")
        elif parts[1].strip().lower() == "on":
            agent.show_logs = True
            logging.disable(logging.NOTSET)
            logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S", force=True)
            print(f"\n  Logs: {green('ON')}\n")
        elif parts[1].strip().lower() == "off":
            agent.show_logs = False
            logging.disable(logging.CRITICAL)
            print(f"\n  Logs: {gray('OFF')}\n")
        else:
            print(f"\n  Usage: {cyan('/logs on')} | {cyan('/logs off')}\n")
        return True

    elif user_input.startswith("/model"):
        parts = user_input.split(maxsplit=1)
        if len(parts) < 2:
            print(f"\n  {bold('Model:')}  {cyan(agent.llm.model)}")
            print(f"  {bold('URL:')}    {gray(agent.llm.base_url)}")
            print(f"\n  Switch: {cyan('/model <name>')}\n")
        else:
            new_model = parts[1].strip()
            agent.llm.model = new_model
            print(f"\n  {green('✓')} Model → {cyan(new_model)}\n")
        return True

    elif user_input == "/config":
        api_display = f"{LLM_API_KEY[:6]}...{LLM_API_KEY[-4:]}" if len(LLM_API_KEY) > 10 else LLM_API_KEY or gray("(not set)")
        print(f"\n  {bold('Configuration')}")
        print(f"    File:      {cyan(USER_CONFIG_FILE)}")
        print(f"    API Key:   {api_display}")
        print(f"    Model:     {cyan(agent.llm.model)}")
        print(f"    Base URL:  {gray(agent.llm.base_url)}")
        print(f"    Agent:     {AGENT_NAME}")
        print(f"    Max iter:  {MAX_ITERATIONS}\n")
        return True

    elif user_input == "/path":
        print(f"\n  {bold('Paths')}")
        print(f"    Home:     {cyan(ARIA_HOME)}")
        print(f"    Config:   {USER_CONFIG_FILE}")
        print(f"    Skills:   {SKILLS_DIR}")
        print(f"    Builtin:  {gray(BUILTIN_SKILLS_DIR)}")
        print(f"    Memory:   {MEMORY_DIR}")
        print(f"    Sessions: {SESSIONS_DIR}")
        print(f"    Source:   {gray(ARIA_SRC)}\n")
        return True

    elif user_input.startswith("/"):
        print(f"\n  {red('✗')} Unknown: {user_input}  {gray('(type / for commands)')}\n")
        return True

    return False


def main():
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
            print(f"  {red('✗')} -e requires a prompt")
            sys.exit(1)

    if not LLM_API_KEY:
        print(f"\n  {red('✗')} No API key configured")
        print(f"  {gray('Set LLM_API_KEY or edit ~/.aria/config.json')}\n")
        sys.exit(1)

    if enable_logs:
        logging.disable(logging.NOTSET)
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S", force=True)

    # Init components (silently)
    llm = LLMClient(api_key=LLM_API_KEY, model=LLM_MODEL, base_url=LLM_BASE_URL)
    skills = SkillRegistry(SKILLS_DIR, builtin_skills_dir=BUILTIN_SKILLS_DIR)
    memory = Memory(MEMORY_DIR)
    session_mgr = SessionManager(SESSIONS_DIR)
    agent = Agent(
        name=AGENT_NAME, llm=llm, skills=skills, memory=memory,
        session_mgr=session_mgr, max_iterations=MAX_ITERATIONS,
    )

    session = session_mgr.create(user_id="default")

    if enable_logs:
        agent.show_logs = True

    # ---- Single prompt mode ----
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
    print_banner(AGENT_NAME, LLM_MODEL, len(skills.skills), session.id)
    prompt_session = _build_prompt_session(session_mgr)

    try:
        while True:
            try:
                active = session_mgr.get_active()
                sid = active.id[:8] if active else "none"
                prompt_str = f"{C.CYAN}{C.BOLD}{AGENT_NAME}{C.RESET} {C.GRAY}{sid}{C.RESET} {C.CYAN}›{C.RESET} "

                if prompt_session:
                    from prompt_toolkit.formatted_text import ANSI
                    user_input = prompt_session.prompt(ANSI(prompt_str)).strip()
                else:
                    user_input = input(prompt_str).strip()
            except EOFError:
                break
            except KeyboardInterrupt:
                print()
                continue

            if not user_input:
                continue

            result = handle_command(user_input, agent, session_mgr, memory, skills)
            if result == "quit":
                break
            elif result:
                continue

            # ── Agent response ───────────────────────────────────
            try:
                print(f"\n  {gray('thinking...')}", end="\r", flush=True)
                response = agent.run(user_input)
                # Clear "thinking..." line
                print("                    ", end="\r")
                # Print response with nice formatting
                for line in response.split("\n"):
                    print(f"  {line}")
                print()
            except Exception as e:
                print(f"\n  {red('✗')} {e}\n")

    except KeyboardInterrupt:
        session_mgr.save_current()
        memory.save_session()
        print(f"\n  {gray('Session saved. Goodbye!')} 👋\n")
    finally:
        llm.close()


if __name__ == "__main__":
    main()
