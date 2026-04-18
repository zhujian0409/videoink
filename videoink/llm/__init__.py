"""LLM provider abstraction for videoink.

v0.1 ships ``OpenAIProvider`` and ``AnthropicProvider``. v0.2 will add
``OpenRouterProvider`` (single-gateway access to many models) and
``OllamaProvider`` (local inference). All providers implement the
``LLMProvider`` protocol from ``base.py``:

    provider.chat(messages, model, temperature=..., max_tokens=...) -> str

``messages`` follows OpenAI's ``[{"role": "system"|"user"|"assistant",
"content": "..."}]`` format; providers translate to their backend's
conventions where necessary (e.g. Anthropic pulls system out).
"""

from .anthropic import AnthropicProvider
from .base import LLMProvider
from .openai import OpenAIProvider

__all__ = ["LLMProvider", "OpenAIProvider", "AnthropicProvider"]
