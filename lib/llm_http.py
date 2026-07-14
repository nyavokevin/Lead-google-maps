"""
lmstudio_api.py
---------------
Lightweight client for LM Studio's local HTTP server.
Replaces the `lmstudio` Python package with direct HTTP calls.

LM Studio exposes an OpenAI-compatible API at:
    http://<host>:<port>/v1/chat/completions

Usage:
    from lmstudio_api import LMStudioClient

    client = LMStudioClient(host="192.168.1.42", port=1234)
    chat = client.Chat("You are a helpful assistant.")
    chat.add_user_message("Hello!")
    response = client.respond(chat, model="llama-3-8b")
    print(response)
"""

import json
import os
import urllib.request
import urllib.error


# ─── Chat history builder ─────────────────────────────────────────────────────

class Chat:
    """Holds a conversation as an ordered list of role/content messages."""

    def __init__(self, system_prompt: str = ""):
        self.messages: list[dict] = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})


# ─── LM Studio HTTP client ────────────────────────────────────────────────────

class LMStudioClient:
    """
    Calls LM Studio's OpenAI-compatible /v1/chat/completions endpoint.

    Args:
        host    : IP or hostname of the machine running LM Studio
                  (e.g. "192.168.1.42" or "localhost")
        port    : Port LM Studio listens on (default 1234)
        timeout : Request timeout in seconds (default 120)
    """

    def __init__(self, host: str = None, port: int = None, timeout: int = 120):
        host = host or os.environ.get("LM_STUDIO_HOST", "192.168.16.104")
        if port is not None:
            port = int(port)
        else:
            port = int(os.environ.get("LM_STUDIO_PORT", "1234"))
        self.base_url = f"http://{host}:{port}/v1"
        self.timeout = timeout

    # ── low-level POST ────────────────────────────────────────────────────────

    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"LM Studio HTTP {e.code} at {url}: {body}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Could not reach LM Studio at {url}: {e.reason}\n"
                "→ Check that LM Studio is running and the host/port are correct."
            ) from e

    # ── list available models ─────────────────────────────────────────────────

    def list_models(self) -> list[str]:
        """Return model IDs currently loaded in LM Studio."""
        url = f"{self.base_url}/models"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            raise RuntimeError(f"Could not list models: {e}") from e

    # ── main inference call ───────────────────────────────────────────────────

    def respond(
        self,
        chat: Chat,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> str:
        """
        Send the conversation to LM Studio and return the assistant reply as a string.

        Args:
            chat        : Chat instance with the conversation history
            model       : Model identifier (must match what's loaded in LM Studio)
            temperature : Sampling temperature (0.0 = deterministic, 1.0 = creative)
            max_tokens  : Maximum tokens to generate
            **kwargs    : Any extra OpenAI-compatible parameters (top_p, stop, etc.)

        Returns:
            The assistant's reply text (stripped).
        """
        payload = {
            "model": model,
            "messages": chat.messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        result = self._post("/chat/completions", payload)

        try:
            return result["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as e:
            raise RuntimeError(
                f"Unexpected response shape from LM Studio: {result}"
            ) from e

    # ── convenience: Chat factory ─────────────────────────────────────────────

    def Chat(self, system_prompt: str = "") -> Chat:
        """Mirrors the lmstudio.Chat() call style for drop-in compatibility."""
        return Chat(system_prompt)