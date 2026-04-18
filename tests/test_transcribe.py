"""Smoke tests for videoink.transcribe — no network, no OpenAI key needed."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from videoink.transcribe import (
    TranscriptResult,
    TranscriptSegment,
    WHISPER_MAX_BYTES,
    _validate_audio,
    transcribe,
)


class TestValidateAudio(unittest.TestCase):
    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            _validate_audio(Path("/nonexistent/videoink/test.m4a"))

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as fh:
            path = Path(fh.name)
        try:
            with self.assertRaisesRegex(ValueError, "empty"):
                _validate_audio(path)
        finally:
            path.unlink()

    def test_too_large(self):
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as fh:
            path = Path(fh.name)
        try:
            path.write_bytes(b"\x00")
            os.truncate(path, WHISPER_MAX_BYTES + 1)
            with self.assertRaisesRegex(ValueError, "25 MB"):
                _validate_audio(path)
        finally:
            path.unlink()

    def test_directory_not_file(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "not a regular file"):
                _validate_audio(Path(d))


class TestTranscriptResult(unittest.TestCase):
    def test_as_dict_with_segments(self):
        seg = TranscriptSegment(start=0.0, end=1.5, text="hello")
        r = TranscriptResult(
            audio_path=Path("/tmp/a.m4a"),
            text="hello world",
            language="en",
            duration=1.5,
            model="whisper-1",
            segments=[seg],
        )
        d = r.as_dict()
        self.assertEqual(d["text"], "hello world")
        self.assertEqual(d["language"], "en")
        self.assertEqual(len(d["segments"]), 1)
        self.assertEqual(d["segments"][0]["text"], "hello")

    def test_empty_segments_default(self):
        r = TranscriptResult(
            audio_path=Path("/tmp/a.m4a"),
            text="",
            language=None,
            duration=None,
            model="whisper-1",
        )
        self.assertEqual(r.segments, [])

    def test_write_json_and_text(self):
        r = TranscriptResult(
            audio_path=Path("/tmp/a.m4a"),
            text="hi there",
            language="en",
            duration=2.0,
            model="whisper-1",
            segments=[TranscriptSegment(0.0, 1.0, "hi"), TranscriptSegment(1.0, 2.0, "there")],
        )
        with tempfile.TemporaryDirectory() as d:
            j = Path(d) / "t.json"
            t = Path(d) / "t.txt"
            r.write_json(j)
            r.write_text(t)
            loaded = json.loads(j.read_text())
            self.assertEqual(loaded["text"], "hi there")
            self.assertEqual(len(loaded["segments"]), 2)
            self.assertEqual(t.read_text().strip(), "hi there")


class TestTranscribeGuards(unittest.TestCase):
    def test_missing_audio_raises_before_network(self):
        with self.assertRaises(FileNotFoundError):
            transcribe(Path("/nonexistent/videoink/x.m4a"))


if __name__ == "__main__":
    unittest.main()
