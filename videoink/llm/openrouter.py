"""OpenRouter LLM provider.

OpenRouter exposes an OpenAI-compatible chat-completions endpoint that
fronts many different model backends (``openai/gpt-4o``,
``anthropic/claude-sonnet-4.5``, ``meta-llama/llama-3.3-70b-instruct``,
…). This provider is a thin wrapper over the ``openai`` SDK pointed at
``https://openrouter.ai/api/v1``.

Environment:
  * ``OPENROUTER_API_KEY`` — API key (or pass ``api_key=...``)
  * ``OPENROUTER_HTTP_REFERER`` — optional, sent as ``HTTP-Referer`` for
    OpenRouter's site-attribution leaderboards
  * ``OPENROUTER_X_TITLE`` — optional, sent as ``X-Title``
"""

from __future__ import annotations

import os
from typing import Any


class OpenRouterProvider:
    name = "openrouter"
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        http_referer: str | None = None,
        x_title: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.http_referer = http_referer or os.getenv("OPENROUTER_HTTP_REFERER")
        self.x_title = x_title or os.getenv("OPENROUTER_X_TITLE")
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise ValueError(
                "Missing OpenRouter API key. Set OPENROUTER_API_KEY or pass api_key="
            )
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenRouterProvider requires the 'openai' package (OpenAI-compatible). "
                "Install: pip install 'videoink[openai]'"
            ) from None
        kwargs: dict[str, Any] = {"api_key": self.api_key, "base_url": self.base_url}
        headers: dict[str, str] = {}
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.x_title:
            headers["X-Title"] = self.x_title
        if headers:
            kwargs["default_headers"] = headers
        self._client = OpenAI(**kwargs)
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
