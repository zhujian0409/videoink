"""Anthropic LLM provider.

Wraps ``client.messages.create`` behind the ``LLMProvider`` protocol.
Handles the OpenAI → Anthropic message-format difference: Anthropic
requires ``system`` as a top-level argument separate from ``messages``.

The ``anthropic`` package is optional; imported lazily in ``chat()``.

Environment:
  * ``ANTHROPIC_API_KEY`` — API key (or pass ``api_key=...``)
  * ``base_url`` — optional, for Anthropic-compatible proxies
"""

from __future__ import annotations

import os
from typing import Any


def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Separate system messages from the main message list.

    OpenAI format puts system in-line as one of the messages. Anthropic
    wants it as a top-level ``system=`` argument. Multiple system
    messages are concatenated with double newlines.
    """
    sys_parts = [m["content"] for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    system_text = "\n\n".join(p for p in sys_parts if p) if sys_parts else None
    return system_text, rest


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = base_url
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "AnthropicProvider requires the 'anthropic' package. "
                "Install: pip install 'videoink[anthropic]'"
            ) from None
        if not self.api_key:
            raise ValueError(
                "Missing Anthropic API key. Set ANTHROPIC_API_KEY or pass api_key="
            )
        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = Anthropic(**kwargs)
        return self._client

    def chat(
        self,
        messages: list[dict],
        model: str,
        *,
        temperature: float | None = None,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """Send chat messages, return the assistant reply text.

        ``max_tokens`` is required by the Anthropic API (unlike OpenAI).
        Default 4096 is a safe middle ground; pass larger for long-form.
        """
        client = self._get_client()
        system_text, rest = _split_system(messages)

        params: dict[str, Any] = {
            "model": model,
            "messages": rest,
            "max_tokens": max_tokens,
        }
        if system_text:
            params["system"] = system_text
        if temperature is not None:
            params["temperature"] = temperature
        params.update(kwargs)

        resp = client.messages.create(**params)
        # resp.content is a list of ContentBlock; concat all text blocks
        parts = [getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"]
        return "".join(parts)
