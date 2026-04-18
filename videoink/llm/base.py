"""LLM provider base protocol.

Every provider implements a minimal ``chat(messages, model, **kwargs)``
returning the assistant text. Keep this surface tiny — we deliberately
do not wrap full chat-completions APIs. Advanced features (tools,
streaming, structured output) are v0.2+.
"""

from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    name: str

    def chat(
        self,
        messages: list[dict],
        model: str,
        **kwargs,
    ) -> str:
        """Send a list of ``{"role", "content"}`` messages, return reply text."""
        ...
