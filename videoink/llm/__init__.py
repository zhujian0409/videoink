"""LLM provider abstraction for videoink.

v0.3 ships four providers: ``OpenAIProvider``, ``AnthropicProvider``,
``OpenRouterProvider`` (single gateway to many models) and
``OllamaProvider`` (local inference). All implement the ``LLMProvider``
protocol from ``base.py``:

    provider.chat(messages, model, temperature=..., max_tokens=...) -> str

``messages`` follows OpenAI's ``[{"role": "system"|"user"|"assistant",
"content": "..."}]`` format; providers translate to their backend's
conventions where necessary (e.g. Anthropic pulls system out).
"""

from .anthropic import AnthropicProvider
from .base import LLMProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from .openrouter import OpenRouterProvider

__all__ = [
    "LLMProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OpenRouterProvider",
    "OllamaProvider",
]
