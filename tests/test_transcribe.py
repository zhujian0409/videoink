"""Smoke tests for videoink.transcribe — no network, no OpenAI key needed."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from videoink import transcribe as transcribe_mod
from videoink.transcribe import (
    TranscriptResult,
    TranscriptSegment,
    WHISPER_MAX_BYTES,
    _stitch_chunk_results,
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


class TestStitchChunkResults(unittest.TestCase):
    def _result(self, segs, duration, lang="en", text=None):
        return TranscriptResult(
            audio_path=Path("/tmp/c.m4a"),
            text=text if text is not None else " ".join(s.text for s in segs),
            language=lang,
            duration=duration,
            model="whisper-1",
            engine="openai",
            segments=segs,
        )

    def test_offsets_segments_by_chunk_start(self):
        a = self._result([TranscriptSegment(0.0, 2.0, "one"), TranscriptSegment(2.0, 4.0, "two")], 4.0)
        b = self._result([TranscriptSegment(0.0, 3.0, "three")], 3.0)
        merged = _stitch_chunk_results(Path("/tmp/full.m4a"), [(0.0, a), (4.0, b)], "whisper-1")
        self.assertEqual([s.start for s in merged.segments], [0.0, 2.0, 4.0])
        self.assertEqual([s.end for s in merged.segments], [2.0, 4.0, 7.0])
        self.assertEqual([s.text for s in merged.segments], ["one", "two", "three"])

    def test_concatenates_text(self):
        a = self._result([TranscriptSegment(0.0, 1.0, "hi")], 1.0, text="hi")
        b = self._result([TranscriptSegment(0.0, 1.0, "there")], 1.0, text="there")
        merged = _stitch_chunk_results(Path("/tmp/f.m4a"), [(0.0, a), (1.0, b)], "whisper-1")
        self.assertEqual(merged.text, "hi there")

    def test_picks_first_language(self):
        a = self._result([], 1.0, lang=None, text="")
        b = self._result([], 1.0, lang="fr", text="bonjour")
        merged = _stitch_chunk_results(Path("/tmp/f.m4a"), [(0.0, a), (1.0, b)], "whisper-1")
        self.assertEqual(merged.language, "fr")

    def test_total_duration_is_last_chunk_end(self):
        a = self._result([], 4.0, text="")
        b = self._result([], 3.5, text="")
        merged = _stitch_chunk_results(Path("/tmp/f.m4a"), [(0.0, a), (4.0, b)], "whisper-1")
        self.assertEqual(merged.duration, 7.5)

    def test_empty_chunks_returns_empty_result(self):
        merged = _stitch_chunk_results(Path("/tmp/f.m4a"), [], "whisper-1")
        self.assertEqual(merged.segments, [])
        self.assertEqual(merged.text, "")
        self.assertIsNone(merged.duration)
        self.assertEqual(merged.engine, "openai")

    def test_preserves_audio_path_and_model(self):
        merged = _stitch_chunk_results(Path("/tmp/original.m4a"), [], "whisper-2")
        self.assertEqual(str(merged.audio_path), "/tmp/original.m4a")
        self.assertEqual(merged.model, "whisper-2")


class TestTranscribeOversizedRouting(unittest.TestCase):
    def test_oversized_openai_routes_to_chunked(self):
        """When engine=openai and audio > 25MB, transcribe() should delegate
        to the chunked path instead of raising."""
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as fh:
            path = Path(fh.name)
        try:
            path.write_bytes(b"\x00")
            os.truncate(path, WHISPER_MAX_BYTES + 1024)
            fake_result = TranscriptResult(
                audio_path=path,
                text="chunked",
                language="en",
                duration=10.0,
                model="whisper-1",
                engine="openai",
            )
            with patch.object(
                transcribe_mod, "_transcribe_openai_chunked", return_value=fake_result
            ) as mocked:
                result = transcribe(path, engine="openai")
            self.assertEqual(result.text, "chunked")
            mocked.assert_called_once()
        finally:
            path.unlink()

    def test_undersized_openai_still_uses_single_call(self):
        """Files under 25MB should NOT route to the chunked path."""
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as fh:
            path = Path(fh.name)
        try:
            path.write_bytes(b"\x00" * 1024)  # 1KB
            fake_result = TranscriptResult(
                audio_path=path, text="single", language="en",
                duration=5.0, model="whisper-1", engine="openai",
            )
            with patch.object(
                transcribe_mod, "_transcribe_openai", return_value=fake_result
            ) as single, patch.object(
                transcribe_mod, "_transcribe_openai_chunked"
            ) as chunked:
                result = transcribe(path, engine="openai")
            self.assertEqual(result.text, "single")
            single.assert_called_once()
            chunked.assert_not_called()
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
