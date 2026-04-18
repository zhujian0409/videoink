"""OpenAI LLM provider.

Wraps ``client.chat.completions.create`` behind the ``LLMProvider`` protocol
in ``base.py``. The ``openai`` package is an optional dependency — it is
imported lazily inside ``chat()`` so importing this module alone does not
require it.

Environment:
  * ``OPENAI_API_KEY`` — API key (or pass ``api_key=...``)
  * ``base_url`` — optional, for OpenAI-compatible proxies (Azure, local)
"""

from __future__ import annotations

import os
from typing import Any


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenAIProvider requires the 'openai' package. "
                "Install: pip install 'videoink[openai]'"
            ) from None
        if not self.api_key:
            raise ValueError(
                "Missing OpenAI API key. Set OPENAI_API_KEY or pass api_key="
            )
        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
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
