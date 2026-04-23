"""Smoke tests for videoink.llm providers — no network, no SDK required."""

import os
import sys
import unittest
from types import ModuleType
from unittest.mock import MagicMock

from videoink.llm.anthropic import AnthropicProvider, _split_system
from videoink.llm.openai import OpenAIProvider
from videoink.llm.ollama import OllamaProvider
from videoink.llm.openrouter import OpenRouterProvider


class TestSplitSystem(unittest.TestCase):
    def test_no_system(self):
        msgs = [{"role": "user", "content": "hi"}]
        sys_text, rest = _split_system(msgs)
        self.assertIsNone(sys_text)
        self.assertEqual(rest, msgs)

    def test_single_system(self):
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ]
        sys_text, rest = _split_system(msgs)
        self.assertEqual(sys_text, "You are helpful.")
        self.assertEqual(rest, [{"role": "user", "content": "hi"}])

    def test_multi_system_concatenated(self):
        msgs = [
            {"role": "system", "content": "Rule 1."},
            {"role": "user", "content": "hi"},
            {"role": "system", "content": "Rule 2."},
        ]
        sys_text, rest = _split_system(msgs)
        self.assertEqual(sys_text, "Rule 1.\n\nRule 2.")
        self.assertEqual(rest, [{"role": "user", "content": "hi"}])

    def test_all_system_only(self):
        msgs = [{"role": "system", "content": "Rules."}]
        sys_text, rest = _split_system(msgs)
        self.assertEqual(sys_text, "Rules.")
        self.assertEqual(rest, [])


class TestOpenAIProviderInit(unittest.TestCase):
    def test_explicit_key(self):
        p = OpenAIProvider(api_key="sk-test")
        self.assertEqual(p.api_key, "sk-test")
        self.assertEqual(p.name, "openai")

    def test_env_key(self):
        old = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "sk-env"
        try:
            p = OpenAIProvider()
            self.assertEqual(p.api_key, "sk-env")
        finally:
            if old is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old

    def test_missing_key_raises_on_client(self):
        old = os.environ.pop("OPENAI_API_KEY", None)
        try:
            p = OpenAIProvider()
            # Inject fake openai module so ImportError doesn't pre-empt.
            fake = ModuleType("openai")
            fake.OpenAI = MagicMock()
            sys.modules["openai"] = fake
            try:
                with self.assertRaisesRegex(ValueError, "Missing OpenAI API key"):
                    p._get_client()
            finally:
                sys.modules.pop("openai", None)
        finally:
            if old is not None:
                os.environ["OPENAI_API_KEY"] = old


class TestAnthropicProviderInit(unittest.TestCase):
    def test_explicit_key(self):
        p = AnthropicProvider(api_key="ant-test")
        self.assertEqual(p.api_key, "ant-test")
        self.assertEqual(p.name, "anthropic")

    def test_env_key(self):
        old = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = "ant-env"
        try:
            p = AnthropicProvider()
            self.assertEqual(p.api_key, "ant-env")
        finally:
            if old is None:
                os.environ.pop("ANTHROPIC_API_KEY", None)
            else:
                os.environ["ANTHROPIC_API_KEY"] = old


class TestOpenAIChatViaFakeSDK(unittest.TestCase):
    """Inject a fake ``openai`` module and verify chat() wiring."""

    def setUp(self):
        fake = ModuleType("openai")
        fake_resp = MagicMock()
        fake_resp.choices = [MagicMock()]
        fake_resp.choices[0].message.content = "hello there"
        self.fake_client = MagicMock()
        self.fake_client.chat.completions.create.return_value = fake_resp
        fake.OpenAI = MagicMock(return_value=self.fake_client)
        self._prev = sys.modules.get("openai")
        sys.modules["openai"] = fake

    def tearDown(self):
        if self._prev is None:
            sys.modules.pop("openai", None)
        else:
            sys.modules["openai"] = self._prev

    def test_chat_returns_content(self):
        p = OpenAIProvider(api_key="sk-fake")
        result = p.chat(
            [{"role": "user", "content": "hi"}],
            model="gpt-4o",
            temperature=0.7,
            max_tokens=100,
        )
        self.assertEqual(result, "hello there")
        # Verify parameters forwarded correctly
        call = self.fake_client.chat.completions.create.call_args
        self.assertEqual(call.kwargs["model"], "gpt-4o")
        self.assertEqual(call.kwargs["temperature"], 0.7)
        self.assertEqual(call.kwargs["max_tokens"], 100)
        self.assertEqual(call.kwargs["messages"], [{"role": "user", "content": "hi"}])

    def test_chat_empty_content_becomes_empty_string(self):
        p = OpenAIProvider(api_key="sk-fake")
        self.fake_client.chat.completions.create.return_value.choices[0].message.content = None
        self.assertEqual(p.chat([{"role": "user", "content": "hi"}], model="gpt-4o"), "")


class TestAnthropicChatViaFakeSDK(unittest.TestCase):
    """Inject a fake ``anthropic`` module and verify chat() wiring."""

    def setUp(self):
        fake = ModuleType("anthropic")
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "claude reply"
        fake_resp = MagicMock()
        fake_resp.content = [text_block]
        self.fake_client = MagicMock()
        self.fake_client.messages.create.return_value = fake_resp
        fake.Anthropic = MagicMock(return_value=self.fake_client)
        self._prev = sys.modules.get("anthropic")
        sys.modules["anthropic"] = fake

    def tearDown(self):
        if self._prev is None:
            sys.modules.pop("anthropic", None)
        else:
            sys.modules["anthropic"] = self._prev

    def test_chat_extracts_system_and_joins_text_blocks(self):
        p = AnthropicProvider(api_key="ant-fake")
        result = p.chat(
            [
                {"role": "system", "content": "Be brief."},
                {"role": "user", "content": "ping"},
            ],
            model="claude-sonnet-4-6",
            max_tokens=200,
        )
        self.assertEqual(result, "claude reply")
        call = self.fake_client.messages.create.call_args
        self.assertEqual(call.kwargs["system"], "Be brief.")
        self.assertEqual(call.kwargs["messages"], [{"role": "user", "content": "ping"}])
        self.assertEqual(call.kwargs["max_tokens"], 200)
        # No system messages mixed into messages=
        self.assertNotIn("system", [m["role"] for m in call.kwargs["messages"]])

    def test_chat_joins_multiple_text_blocks(self):
        block1 = MagicMock(); block1.type = "text"; block1.text = "part1 "
        block2 = MagicMock(); block2.type = "text"; block2.text = "part2"
        non_text = MagicMock(); non_text.type = "tool_use"; non_text.text = "ignored"
        self.fake_client.messages.create.return_value.content = [block1, non_text, block2]
        p = AnthropicProvider(api_key="ant-fake")
        result = p.chat([{"role": "user", "content": "hi"}], model="claude-sonnet-4-6")
        self.assertEqual(result, "part1 part2")


class TestOpenRouterProviderInit(unittest.TestCase):
    def test_name(self):
        self.assertEqual(OpenRouterProvider(api_key="or-x").name, "openrouter")

    def test_explicit_key(self):
        p = OpenRouterProvider(api_key="or-test")
        self.assertEqual(p.api_key, "or-test")

    def test_env_key(self):
        old = os.environ.get("OPENROUTER_API_KEY")
        os.environ["OPENROUTER_API_KEY"] = "or-env"
        try:
            p = OpenRouterProvider()
            self.assertEqual(p.api_key, "or-env")
        finally:
            if old is None:
                os.environ.pop("OPENROUTER_API_KEY", None)
            else:
                os.environ["OPENROUTER_API_KEY"] = old

    def test_default_base_url(self):
        p = OpenRouterProvider(api_key="or-x")
        self.assertEqual(p.base_url, "https://openrouter.ai/api/v1")

    def test_override_base_url(self):
        p = OpenRouterProvider(api_key="or-x", base_url="https://alt.example/api/v1")
        self.assertEqual(p.base_url, "https://alt.example/api/v1")

    def test_missing_key_raises_distinct_message(self):
        old = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            p = OpenRouterProvider()
            fake = ModuleType("openai"); fake.OpenAI = MagicMock()
            sys.modules["openai"] = fake
            try:
                with self.assertRaisesRegex(ValueError, "OpenRouter API key"):
                    p._get_client()
            finally:
                sys.modules.pop("openai", None)
        finally:
            if old is not None:
                os.environ["OPENROUTER_API_KEY"] = old


class TestOpenRouterChatViaFakeSDK(unittest.TestCase):
    def setUp(self):
        fake = ModuleType("openai")
        fake_resp = MagicMock()
        fake_resp.choices = [MagicMock()]
        fake_resp.choices[0].message.content = "router reply"
        self.fake_client = MagicMock()
        self.fake_client.chat.completions.create.return_value = fake_resp
        self.openai_ctor = MagicMock(return_value=self.fake_client)
        fake.OpenAI = self.openai_ctor
        self._prev = sys.modules.get("openai")
        sys.modules["openai"] = fake

    def tearDown(self):
        if self._prev is None:
            sys.modules.pop("openai", None)
        else:
            sys.modules["openai"] = self._prev

    def test_client_built_with_openrouter_base_url(self):
        p = OpenRouterProvider(api_key="or-fake")
        p.chat([{"role": "user", "content": "hi"}], model="anthropic/claude-sonnet-4.5")
        ctor_call = self.openai_ctor.call_args
        self.assertEqual(ctor_call.kwargs["api_key"], "or-fake")
        self.assertEqual(ctor_call.kwargs["base_url"], "https://openrouter.ai/api/v1")

    def test_chat_returns_content(self):
        p = OpenRouterProvider(api_key="or-fake")
        out = p.chat(
            [{"role": "user", "content": "hi"}],
            model="meta-llama/llama-3.3-70b-instruct",
            temperature=0.3,
        )
        self.assertEqual(out, "router reply")
        call = self.fake_client.chat.completions.create.call_args
        self.assertEqual(call.kwargs["model"], "meta-llama/llama-3.3-70b-instruct")
        self.assertEqual(call.kwargs["temperature"], 0.3)

    def test_optional_attribution_headers(self):
        p = OpenRouterProvider(
            api_key="or-fake",
            http_referer="https://example.com",
            x_title="videoink",
        )
        p.chat([{"role": "user", "content": "hi"}], model="openai/gpt-4o-mini")
        ctor_kwargs = self.openai_ctor.call_args.kwargs
        self.assertEqual(
            ctor_kwargs["default_headers"],
            {"HTTP-Referer": "https://example.com", "X-Title": "videoink"},
        )

    def test_no_headers_by_default(self):
        p = OpenRouterProvider(api_key="or-fake")
        p.chat([{"role": "user", "content": "hi"}], model="openai/gpt-4o-mini")
        self.assertNotIn("default_headers", self.openai_ctor.call_args.kwargs)


class TestOllamaProviderInit(unittest.TestCase):
    def test_name(self):
        self.assertEqual(OllamaProvider().name, "ollama")

    def test_default_base_url(self):
        old = os.environ.pop("OLLAMA_HOST", None)
        try:
            self.assertEqual(OllamaProvider().base_url, "http://localhost:11434/v1")
        finally:
            if old is not None:
                os.environ["OLLAMA_HOST"] = old

    def test_env_host_honoured(self):
        old = os.environ.get("OLLAMA_HOST")
        os.environ["OLLAMA_HOST"] = "gpu-box:11434"
        try:
            p = OllamaProvider()
            self.assertEqual(p.base_url, "http://gpu-box:11434/v1")
        finally:
            if old is None:
                os.environ.pop("OLLAMA_HOST", None)
            else:
                os.environ["OLLAMA_HOST"] = old

    def test_env_host_with_scheme_preserved(self):
        old = os.environ.get("OLLAMA_HOST")
        os.environ["OLLAMA_HOST"] = "https://ollama.example.com:8443"
        try:
            p = OllamaProvider()
            self.assertEqual(p.base_url, "https://ollama.example.com:8443/v1")
        finally:
            if old is None:
                os.environ.pop("OLLAMA_HOST", None)
            else:
                os.environ["OLLAMA_HOST"] = old

    def test_override_base_url_wins(self):
        old = os.environ.get("OLLAMA_HOST")
        os.environ["OLLAMA_HOST"] = "should-be-ignored"
        try:
            p = OllamaProvider(base_url="http://override/v1")
            self.assertEqual(p.base_url, "http://override/v1")
        finally:
            if old is None:
                os.environ.pop("OLLAMA_HOST", None)
            else:
                os.environ["OLLAMA_HOST"] = old


class TestOllamaChatViaFakeSDK(unittest.TestCase):
    def setUp(self):
        fake = ModuleType("openai")
        fake_resp = MagicMock()
        fake_resp.choices = [MagicMock()]
        fake_resp.choices[0].message.content = "local llama reply"
        self.fake_client = MagicMock()
        self.fake_client.chat.completions.create.return_value = fake_resp
        self.openai_ctor = MagicMock(return_value=self.fake_client)
        fake.OpenAI = self.openai_ctor
        self._prev = sys.modules.get("openai")
        sys.modules["openai"] = fake

    def tearDown(self):
        if self._prev is None:
            sys.modules.pop("openai", None)
        else:
            sys.modules["openai"] = self._prev

    def test_client_uses_localhost_and_placeholder_key(self):
        old = os.environ.pop("OLLAMA_HOST", None)
        try:
            p = OllamaProvider()
            p.chat([{"role": "user", "content": "hi"}], model="llama3.2")
            kwargs = self.openai_ctor.call_args.kwargs
            self.assertEqual(kwargs["base_url"], "http://localhost:11434/v1")
            # Ollama doesn't enforce a key; SDK still requires non-empty — we pass a sentinel
            self.assertTrue(kwargs["api_key"])
        finally:
            if old is not None:
                os.environ["OLLAMA_HOST"] = old

    def test_chat_returns_content(self):
        p = OllamaProvider()
        out = p.chat(
            [{"role": "user", "content": "hi"}],
            model="qwen2.5:7b",
            temperature=0.4,
            max_tokens=500,
        )
        self.assertEqual(out, "local llama reply")
        call = self.fake_client.chat.completions.create.call_args
        self.assertEqual(call.kwargs["model"], "qwen2.5:7b")
        self.assertEqual(call.kwargs["temperature"], 0.4)
        self.assertEqual(call.kwargs["max_tokens"], 500)


if __name__ == "__main__":
    unittest.main()
