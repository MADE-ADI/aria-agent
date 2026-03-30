"""
Harbor agent adapter for Aria AI agent.

Implements the BaseInstalledAgent interface to run Aria
in Terminal-Bench evaluations via Harbor.

Aria operates as a terminal agent: it receives an instruction,
reasons about it, and executes bash commands to complete the task.
"""

import json
import os
import shlex
from pathlib import Path

from harbor.agents.installed.base import BaseInstalledAgent, ExecInput
from harbor.models.agent.context import AgentContext
from harbor.models.trial.paths import EnvironmentPaths


class AriaAgent(BaseInstalledAgent):
    """
    Harbor agent adapter for Aria.

    In terminal-bench mode, Aria runs as a headless agent that
    takes instructions and executes bash commands through an
    LLM-driven agentic loop.
    """

    @staticmethod
    def name() -> str:
        return "aria"

    @property
    def _install_agent_template_path(self) -> Path:
        return Path(__file__).parent / "install-aria.sh.j2"

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        escaped_instruction = shlex.quote(instruction)

        env: dict[str, str] = {}

        # Support multiple LLM providers
        for key in [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "LLM_API_KEY",
            "LLM_BASE_URL",
            "LLM_MODEL",
        ]:
            if key in os.environ:
                env[key] = os.environ[key]

        # Build model config
        model_env = ""
        if self.model_name:
            provider, model = self._parse_model_name(self.model_name)
            # Map provider to API key env var and base URL
            provider_map = {
                "anthropic": ("ANTHROPIC_API_KEY", "https://api.anthropic.com/v1"),
                "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1"),
                "google": ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta"),
            }
            if provider in provider_map:
                key_name, base_url = provider_map[provider]
                if key_name in os.environ:
                    env["LLM_API_KEY"] = os.environ[key_name]
                env["LLM_BASE_URL"] = base_url
            env["LLM_MODEL"] = model

        output_dir = EnvironmentPaths.agent_dir
        output_file = output_dir / "aria-output.jsonl"

        return [
            ExecInput(
                command=f"mkdir -p {output_dir}",
                env=env,
            ),
            ExecInput(
                command=(
                    f"python3 /opt/aria/terminal_agent.py "
                    f"--output {output_file} "
                    f"{escaped_instruction} "
                    f"2>&1 | tee {output_dir}/aria-log.txt"
                ),
                env=env,
            ),
        ]

    def _parse_model_name(self, model_name: str) -> tuple[str, str]:
        """Parse Harbor model format (provider/model) into provider and model."""
        if "/" in model_name:
            parts = model_name.split("/", 1)
            return parts[0], parts[1]
        return "openai", model_name

    def populate_context_post_run(self, context: AgentContext) -> None:
        """
        Populate the agent context with token usage from Aria's output.
        """
        output_file = self.logs_dir / "aria-output.jsonl"

        if not output_file.exists():
            print(f"Aria output file not found: {output_file}")
            return

        total_input_tokens = 0
        total_output_tokens = 0

        with open(output_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get("type") == "llm_call":
                        usage = event.get("usage", {})
                        total_input_tokens += usage.get("input_tokens", 0)
                        total_output_tokens += usage.get("output_tokens", 0)
                except json.JSONDecodeError:
                    continue

        context.n_input_tokens = total_input_tokens
        context.n_output_tokens = total_output_tokens
