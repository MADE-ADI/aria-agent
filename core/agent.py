"""
Agent — the agentic loop that reasons, plans, and executes skills.
Now with session support.
"""
import json
import logging
from typing import Any

from core.llm import LLMClient
from core.skills import SkillRegistry
from core.memory import Memory
from core.session import Session, SessionManager

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are {name}, a personal AI agent. You help the user by reasoning step-by-step and using tools when needed.

## Session
Current session: {session_id}
User: {user_id}

## Available Skills
{skills_list}

## How to Use Tools
When you need to use a skill, respond with ONLY the JSON tool call — no extra text:
{{"tool": "skill_name", "args": {{"param": "value"}}}}

## Guidelines
- Think step-by-step before acting
- Use skills when they match the user's request
- If no skill matches, answer directly with your knowledge
- Be concise and helpful
- If a task needs multiple steps, plan them out first
- After executing a skill, summarize the result for the user

## Formatting
- NEVER use markdown (no **, ##, ```, tables, etc.)
- Output is displayed in a terminal — use plain text only
- Use dashes (-) for lists, CAPS or quotes for emphasis
- Use simple spacing and indentation for structure

## Memory
You can remember things for the user. If they ask you to remember something, use the 'remember' skill.
You have access to these recalled facts:
{recalled_facts}
"""


class Agent:
    """Agentic loop: reason → plan → act → observe → repeat."""

    def __init__(
        self,
        name: str,
        llm: LLMClient,
        skills: SkillRegistry,
        memory: Memory,
        session_mgr: SessionManager,
        max_iterations: int = 10,
    ):
        self.name = name
        self.llm = llm
        self.skills = skills
        self.memory = memory
        self.session_mgr = session_mgr
        self.max_iterations = max_iterations
        self.show_logs = False  # toggle with /logs on|off

    def _ensure_session(self, user_id: str = "default") -> Session:
        """Ensure there's an active session, create one if not."""
        session = self.session_mgr.get_active()
        if not session:
            session = self.session_mgr.create(user_id=user_id)
        return session

    def _build_system(self, user_input: str, session: Session) -> str:
        skills_text = ""
        for s in self.skills.list_all():
            skills_text += f"- **{s['name']}**: {s['description']} (triggers: {', '.join(s['triggers'])})\n"
        if not skills_text:
            skills_text = "(no skills loaded)\n"

        # Recall relevant memories
        facts = self.memory.recall(user_input, limit=5)
        facts_text = "\n".join(f"- {f}" for f in facts) if facts else "(none)"

        return SYSTEM_PROMPT.format(
            name=self.name,
            session_id=session.id,
            user_id=session.user_id,
            skills_list=skills_text,
            recalled_facts=facts_text,
        )

    def _parse_tool_call(self, text: str) -> tuple[str, dict] | None:
        """Try to extract a tool call from the LLM response."""
        import re

        # Try direct parse (entire response is JSON)
        try:
            data = json.loads(text.strip())
            if "tool" in data:
                return data["tool"], data.get("args", {})
        except (json.JSONDecodeError, KeyError):
            pass

        # Try to find JSON in markdown code block
        pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if "tool" in data:
                    return data["tool"], data.get("args", {})
            except (json.JSONDecodeError, KeyError):
                pass

        # Try to find inline JSON object with "tool" key anywhere in text
        pattern2 = r'(\{"tool"\s*:\s*"[^"]+"\s*,\s*"args"\s*:\s*\{[^}]*\}\s*\})'
        match2 = re.search(pattern2, text)
        if match2:
            try:
                data = json.loads(match2.group(1))
                if "tool" in data:
                    return data["tool"], data.get("args", {})
            except (json.JSONDecodeError, KeyError):
                pass

        return None

    def _log(self, msg: str):
        """Print log if show_logs is enabled."""
        if self.show_logs:
            print(f"\033[90m  [log] {msg}\033[0m")

    def run(self, user_input: str, user_id: str = "default") -> str:
        """Process user input through the agentic loop."""
        session = self._ensure_session(user_id)
        session.add_message("user", user_input)
        self.memory.add_message("user", user_input)

        system_msg = self._build_system(user_input, session)
        messages = [{"role": "system", "content": system_msg}]

        # Use session messages for context (preserves history across runs)
        messages.extend(session.get_messages(last_n=30))
        self._log(f"Session: {session.id} | Context: {len(messages)} messages")

        for iteration in range(self.max_iterations):
            self._log(f"Iteration {iteration + 1}/{self.max_iterations}")
            self._log(f"Sending to LLM ({self.llm.model})...")

            response = self.llm.chat(messages)
            content = response.get("content", "")

            self._log(f"LLM response: {len(content)} chars")

            # Check for tool call
            tool_call = self._parse_tool_call(content)

            if tool_call is None:
                self._log("No tool call — returning final answer")
                # No tool call — this is the final answer
                session.add_message("assistant", content)
                self.memory.add_message("assistant", content)
                self.session_mgr.save_current()
                return content

            tool_name, tool_args = tool_call
            self._log(f"Tool call: {tool_name}({json.dumps(tool_args, ensure_ascii=False)})")

            # Execute the skill
            skill = self.skills.get(tool_name)
            if skill is None:
                observation = f"Error: skill '{tool_name}' not found."
                self._log(f"Skill not found: {tool_name}")
            else:
                try:
                    self._log(f"Executing skill: {tool_name}...")
                    result = skill.execute(**tool_args)
                    observation = json.dumps(result, ensure_ascii=False) if isinstance(result, (dict, list)) else str(result)
                    self._log(f"Skill result: {observation[:150]}...")
                except Exception as e:
                    observation = f"Error executing {tool_name}: {e}"
                    self._log(f"Skill error: {e}")

            # Feed observation back into the loop
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": f"[Tool Result for {tool_name}]\n{observation}\n\nNow provide your response to the user based on this result.",
            })

        # Max iterations hit
        self._log(f"Max iterations ({self.max_iterations}) reached")
        final = "I've reached my thinking limit. Here's what I have so far based on the last response."
        session.add_message("assistant", final)
        self.memory.add_message("assistant", final)
        self.session_mgr.save_current()
        return final
