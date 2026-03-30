"""
Harbor agent adapter for Aria AI agent.

Implements BaseInstalledAgent for Terminal-Bench 2.0 evaluations via Harbor.
"""

import json
import os
import shlex
from pathlib import Path

from harbor.agents.installed.base import BaseInstalledAgent, with_prompt_template
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


class AriaAgent(BaseInstalledAgent):
    """Harbor adapter for Aria terminal agent."""

    @staticmethod
    def name() -> str:
        return "aria"

    async def install(self, environment: BaseEnvironment) -> None:
        """Install Aria and dependencies in the container."""
        # Install system deps
        await self.exec_as_root(
            environment,
            command="apt-get update && apt-get install -y python3 python3-pip curl jq",
        )
        # Install Python deps
        await self.exec_as_root(
            environment,
            command="pip3 install --break-system-packages httpx 2>/dev/null || pip3 install httpx",
        )
        # Copy terminal agent into container
        agent_src = Path(__file__).parent / "terminal_agent.py"
        await self.exec_as_root(environment, command="mkdir -p /opt/aria")
        # Upload agent file via base64 encoding
        import base64
        agent_code = agent_src.read_text()
        encoded = base64.b64encode(agent_code.encode()).decode()
        await self.exec_as_root(
            environment,
            command=f"echo '{encoded}' | base64 -d > /opt/aria/terminal_agent.py && chmod +x /opt/aria/terminal_agent.py",
        )
        # Verify
        await self.exec_as_agent(
            environment,
            command="python3 /opt/aria/terminal_agent.py --help",
        )

    @with_prompt_template
    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        """Run Aria agent on the task."""
        escaped_instruction = shlex.quote(instruction)

        env: dict[str, str] = {}

        # Pass through API keys from host environment
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

        # Map Harbor model format to env vars
        if self.model_name:
            provider, model = self._parse_model_name(self.model_name)
            provider_map = {
                "anthropic": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "google": "GEMINI_API_KEY",
            }
            if provider in provider_map:
                key_name = provider_map[provider]
                if key_name in os.environ:
                    env["LLM_API_KEY"] = os.environ[key_name]

            # Set base URL for provider
            base_urls = {
                "anthropic": "https://api.anthropic.com/v1",
                "openai": "https://api.openai.com/v1",
                "google": "https://generativelanguage.googleapis.com/v1beta",
            }
            if provider in base_urls:
                env["LLM_BASE_URL"] = base_urls[provider]

            env["LLM_MODEL"] = model

        output_dir = "/tmp/aria-output"
        output_file = f"{output_dir}/aria-output.jsonl"

        await self.exec_as_agent(environment, command=f"mkdir -p {output_dir}", env=env)

        await self.exec_as_agent(
            environment,
            command=(
                f"python3 /opt/aria/terminal_agent.py "
                f"--output {output_file} "
                f"{escaped_instruction} "
                f"2>&1 | tee {output_dir}/aria-log.txt"
            ),
            env=env,
        )

    def _parse_model_name(self, model_name: str) -> tuple[str, str]:
        if "/" in model_name:
            parts = model_name.split("/", 1)
            return parts[0], parts[1]
        return "openai", model_name

    def populate_context_post_run(self, context: AgentContext) -> None:
        """Extract token usage from Aria's output logs."""
        output_file = self.logs_dir / "aria-output.jsonl"

        if not output_file.exists():
            # Try alternative location
            alt = self.logs_dir / "aria-log.txt"
            if alt.exists():
                print(f"[aria] Found log at {alt} but no JSONL metrics")
            return

        total_input = 0
        total_output = 0

        with open(output_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get("type") == "llm_call":
                        usage = event.get("usage", {})
                        total_input += usage.get("input_tokens", 0)
                        total_output += usage.get("output_tokens", 0)
                except json.JSONDecodeError:
                    continue

        context.n_input_tokens = total_input
        context.n_output_tokens = total_output
