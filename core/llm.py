"""
LLM client — unified interface for calling language models.
"""
import json
import logging
import httpx

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around OpenAI-compatible chat completion API."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://api.openai.com").rstrip("/")
        self.client = httpx.Client(timeout=120)

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> dict:
        """Send chat completion request. Returns the assistant message dict."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        # Auto-detect: if base_url already ends with /v1, don't double it
        if self.base_url.rstrip("/").endswith("/v1"):
            url = f"{self.base_url}/chat/completions"
        else:
            url = f"{self.base_url}/v1/chat/completions"
        logger.debug(f"LLM request → {self.model} ({len(messages)} msgs)")

        resp = self.client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]

    def close(self):
        self.client.close()
