"""Ollama LLM provider — fully local inference.

Ollama exposes an OpenAI-compatible chat-completions endpoint on
``http://localhost:11434/v1``. This provider wires the ``openai`` SDK
to that endpoint; no network traffic leaves your machine (or your
homelab / private VPC, depending on where Ollama runs).

Environment:
  * ``OLLAMA_HOST`` — host[:port] or full URL. Examples:
      ``gpu-box:11434``, ``https://ollama.example.com:8443``.
      If omitted, defaults to ``localhost:11434``.

No API key is required, but the ``openai`` SDK insists on a non-empty
string, so this provider sends the sentinel ``"ollama"`` (or whatever
you pass as ``api_key=``) which Ollama ignores.
"""

from __future__ import annotations

import os
from typing import Any


DEFAULT_HOST = "localhost:11434"
_PLACEHOLDER_KEY = "ollama"


def _resolve_base_url(host: str) -> str:
    """Turn a bare host, host:port, or full URL into ``<scheme>://<host>/v1``."""
    host = host.strip().rstrip("/")
    if host.startswith(("http://", "https://")):
        return f"{host}/v1"
    return f"http://{host}/v1"


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or _PLACEHOLDER_KEY
        if base_url is not None:
            self.base_url = base_url
        else:
            host = os.getenv("OLLAMA_HOST") or DEFAULT_HOST
            self.base_url = _resolve_base_url(host)
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OllamaProvider requires the 'openai' package (OpenAI-compatible). "
                "Install: pip install 'videoink[openai]'"
            ) from None
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def chat(
        self,
        messages: list[dict],
        model: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Send chat-completion messages, return the assistant reply text."""
        client = self._get_client()
        params: dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        params.update(kwargs)

        resp = client.chat.completions.create(**params)
        return resp.choices[0].message.content or ""
