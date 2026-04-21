"""Tests for the full pipeline helpers — network-heavy orchestration is
covered via real e2e runs, not unit tests; this file just locks down
the pure helpers."""

import unittest

from videoink.cli import _sanitize_slug


class TestSanitizeSlug(unittest.TestCase):
    def test_youtube_id(self):
        self.assertEqual(_sanitize_slug("aqz-KE-bpKQ"), "aqz-KE-bpKQ")

    def test_bilibili_bvid(self):
        self.assertEqual(_sanitize_slug("BV1gQDCBNE3m"), "BV1gQDCBNE3m")

    def test_spaces_become_dashes(self):
        self.assertEqual(_sanitize_slug("Big Buck Bunny"), "Big-Buck-Bunny")

    def test_punctuation_collapses(self):
        self.assertEqual(_sanitize_slug("Hello, World!"), "Hello-World")

    def test_multiple_specials_collapse_to_single_dash(self):
        self.assertEqual(_sanitize_slug("a   b!!!c"), "a-b-c")

    def test_chinese_falls_back_to_video(self):
        # all non-ASCII → stripped → empty → fallback
        self.assertEqual(_sanitize_slug("视频标题"), "video")

    def test_leading_trailing_dashes_stripped(self):
        self.assertEqual(_sanitize_slug("---xyz---"), "xyz")

    def test_empty(self):
        self.assertEqual(_sanitize_slug(""), "video")

    def test_whitespace_only(self):
        self.assertEqual(_sanitize_slug("   "), "video")

    def test_preserves_underscore_and_dash(self):
        self.assertEqual(_sanitize_slug("a_b-c"), "a_b-c")

    def test_none_safe(self):
        # defensive: ``str | None`` may be None from upstream .get()
        self.assertEqual(_sanitize_slug(None), "video")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
