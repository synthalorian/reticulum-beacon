"""AI Bot — integrates with an OpenAI-compatible LLM API for conversational responses.

Configured via environment variables:
- BEACON_AI_API_KEY: API key (default: none, uses local inference)
- BEACON_AI_API_URL: API endpoint URL (default: http://localhost:11434/v1/chat/completions)
- BEACON_AI_MODEL: Model name (default: llama3.2)
- BEACON_AI_PREFIX: Message prefix to trigger the bot (default: /ai)
"""

import json
import os
import urllib.error
import urllib.request

from .base import BeaconBot


class AIBot(BeaconBot):
    name = "ai"
    description = "AI assistant powered by an OpenAI-compatible LLM API"
    version = "0.1.0"

    def __init__(self, propagation_node=None):
        super().__init__(propagation_node)
        self.api_key = os.environ.get("BEACON_AI_API_KEY", "")
        self.api_url = os.environ.get(
            "BEACON_AI_API_URL",
            "http://localhost:11434/v1/chat/completions",
        )
        self.model = os.environ.get("BEACON_AI_MODEL", "llama3.2")
        self.prefix = os.environ.get("BEACON_AI_PREFIX", "/ai")
        self._conversations: dict[str, list[dict]] = {}

    def on_message(self, message) -> None:
        content = getattr(message, "content", b"")
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        if not content.strip().lower().startswith(self.prefix.lower()):
            return

        # Strip prefix to get the actual prompt
        prompt = content[len(self.prefix) :].strip()
        if not prompt:
            self.reply(message, content="Please provide a prompt after /ai", title="AI Response")
            return

        # Get or create conversation context
        sender_key = message.source_hash.hex() if hasattr(message, "source_hash") else "default"
        if sender_key not in self._conversations:
            self._conversations[sender_key] = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant running on a Reticulum mesh network node. Keep responses concise and informative.",
                }
            ]

        self._conversations[sender_key].append({"role": "user", "content": prompt})

        try:
            response_text = self._query_llm(self._conversations[sender_key])
            self._conversations[sender_key].append({"role": "assistant", "content": response_text})

            # Trim conversation history to last 20 messages
            if len(self._conversations[sender_key]) > 20:
                self._conversations[sender_key] = [
                    self._conversations[sender_key][0],
                    *self._conversations[sender_key][-19:],
                ]

            self.reply(message, content=response_text, title="AI Response")

        except Exception as e:
            self.reply(
                message,
                content=f"Error querying AI: {e}",
                title="AI Error",
            )

    def _query_llm(self, messages: list[dict]) -> str:
        """Send a chat completion request to the API."""
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "max_tokens": 1024,
                "temperature": 0.7,
            }
        ).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(
            self.api_url,
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            # Redact any API key that might be in the error response body
            if self.api_key:
                error_body = error_body.replace(self.api_key, "***")
            raise RuntimeError(f"API returned status {e.code}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Could not reach LLM API: {e.reason}") from e
