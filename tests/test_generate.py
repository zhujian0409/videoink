"""Smoke tests for videoink.generate — no network calls."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from videoink.generate import (
    BUNDLED_STYLES,
    GenerateResult,
    _build_messages,
    _load_style,
    _load_transcript,
    generate_article,
)


class TestLoadStyle(unittest.TestCase):
    def test_bundled_default(self):
        md = _load_style("default")
        self.assertIn("default style", md)
        self.assertIn("Rules", md)

    def test_bundled_technical(self):
        md = _load_style("technical")
        self.assertIn("technical", md.lower())

    def test_missing_raises(self):
        with self.assertRaisesRegex(FileNotFoundError, "not found"):
            _load_style("bogus-nonexistent")

    def test_override_dir_tried_first(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "default.md").write_text("CUSTOM OVERRIDE")
            md = _load_style("default", styles_dir=Path(d))
            self.assertEqual(md, "CUSTOM OVERRIDE")

    def test_override_dir_falls_back_to_bundled(self):
        with tempfile.TemporaryDirectory() as d:
            # d is empty → should fall back to bundled
            md = _load_style("default", styles_dir=Path(d))
            self.assertIn("default style", md)

    def test_bundled_styles_dir_has_files(self):
        self.assertTrue((BUNDLED_STYLES / "default.md").is_file())
        self.assertTrue((BUNDLED_STYLES / "technical.md").is_file())


class TestLoadTranscript(unittest.TestCase):
    def test_from_dict(self):
        text, src = _load_transcript({"text": "hi there", "language": "en"})
        self.assertEqual(text, "hi there")
        self.assertEqual(src, "<in-memory>")

    def test_from_dict_missing_text_key(self):
        text, src = _load_transcript({"language": "en"})
        self.assertEqual(text, "")

    def test_from_transcript_result(self):
        from videoink.transcribe import TranscriptResult
        r = TranscriptResult(
            audio_path=Path("/tmp/x.m4a"),
            text="spoken",
            language="en",
            duration=2.0,
            model="whisper-1",
        )
        text, src = _load_transcript(r)
        self.assertEqual(text, "spoken")
        self.assertIn("x.m4a", src)

    def test_from_json_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"text": "from file"}, fh)
            path = Path(fh.name)
        try:
            text, src = _load_transcript(path)
            self.assertEqual(text, "from file")
            self.assertEqual(src, str(path))
        finally:
            path.unlink()

    def test_json_path_as_string(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"text": "stringy"}, fh)
            path = Path(fh.name)
        try:
            text, _ = _load_transcript(str(path))
            self.assertEqual(text, "stringy")
        finally:
            path.unlink()

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            _load_transcript(Path("/nonexistent/videoink/x.json"))

    def test_directory_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                _load_transcript(Path(d))

    def test_wrong_type_raises(self):
        with self.assertRaises(TypeError):
            _load_transcript(42)

    def test_json_file_list_root_raises_value_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(["a", "b", "c"], fh)
            path = Path(fh.name)
        try:
            with self.assertRaisesRegex(ValueError, "transcript JSON"):
                _load_transcript(path)
        finally:
            path.unlink()

    def test_json_file_scalar_root_raises_value_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump("just a string", fh)
            path = Path(fh.name)
        try:
            with self.assertRaisesRegex(ValueError, "transcript JSON"):
                _load_transcript(path)
        finally:
            path.unlink()


class TestBuildMessages(unittest.TestCase):
    def test_shape(self):
        msgs = _build_messages("STYLE_X", "TRANSCRIPT_Y")
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[1]["role"], "user")
        self.assertIn("STYLE_X", msgs[0]["content"])
        self.assertIn("TRANSCRIPT_Y", msgs[1]["content"])
        self.assertIn("Markdown only", msgs[1]["content"])


class TestGenerateResult(unittest.TestCase):
    def test_as_dict(self):
        r = GenerateResult(
            article_md="# Title\n\nBody.",
            provider_name="openai",
            model="gpt-4o",
            style="default",
            transcript_source="/tmp/t.json",
        )
        d = r.as_dict()
        self.assertEqual(d["provider_name"], "openai")
        self.assertEqual(d["model"], "gpt-4o")
        self.assertIn("Title", d["article_md"])

    def test_write_adds_trailing_newline(self):
        r = GenerateResult(
            article_md="# Title",
            provider_name="x",
            model="y",
            style="z",
            transcript_source="s",
        )
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "a" / "b" / "z.md"
            r.write(out)
            content = out.read_text()
            self.assertTrue(content.endswith("\n"))
            self.assertEqual(content, "# Title\n")

    def test_write_preserves_existing_newline(self):
        r = GenerateResult(
            article_md="# Title\n\nBody\n",
            provider_name="x",
            model="y",
            style="z",
            transcript_source="s",
        )
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "z.md"
            r.write(out)
            self.assertEqual(out.read_text(), "# Title\n\nBody\n")


class TestGenerateArticleE2E(unittest.TestCase):
    def test_with_mock_provider(self):
        fake = MagicMock()
        fake.name = "fake-provider"
        fake.chat.return_value = "  # Title\n\nArticle body.  "

        result = generate_article(
            transcript={"text": "some transcript"},
            provider=fake,
            model="fake-model",
            style="default",
            temperature=0.5,
            max_tokens=2000,
        )
        self.assertEqual(result.provider_name, "fake-provider")
        self.assertEqual(result.model, "fake-model")
        self.assertEqual(result.style, "default")
        self.assertTrue(result.article_md.startswith("# Title"))
        self.assertFalse(result.article_md.endswith(" "))  # strip()

        call = fake.chat.call_args
        # messages is positional
        msgs = call.args[0]
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[1]["role"], "user")
        # model positional
        self.assertEqual(call.args[1], "fake-model")
        # kwargs
        self.assertEqual(call.kwargs["temperature"], 0.5)
        self.assertEqual(call.kwargs["max_tokens"], 2000)

    def test_empty_transcript_text_raises(self):
        fake = MagicMock()
        with self.assertRaisesRegex(ValueError, "empty"):
            generate_article(
                transcript={"text": "   "},
                provider=fake,
                model="x",
            )
        fake.chat.assert_not_called()

    def test_provider_without_name_attribute(self):
        fake = MagicMock(spec=["chat"])  # no .name attribute
        fake.chat.return_value = "# X\n"
        result = generate_article(
            transcript={"text": "t"}, provider=fake, model="m",
        )
        self.assertEqual(result.provider_name, "unknown")

    def test_style_from_override_dir(self):
        fake = MagicMock()
        fake.name = "p"
        fake.chat.return_value = "# T\n"
        with tempfile.TemporaryDirectory() as d:
            Path(d, "custom.md").write_text("MY RULES")
            result = generate_article(
                transcript={"text": "t"},
                provider=fake,
                model="m",
                style="custom",
                styles_dir=Path(d),
            )
            self.assertEqual(result.style, "custom")
            # Verify style content was injected into system message
            msgs = fake.chat.call_args.args[0]
            self.assertIn("MY RULES", msgs[0]["content"])


if __name__ == "__main__":
    unittest.main()
