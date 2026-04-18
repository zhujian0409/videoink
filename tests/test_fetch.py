"""Smoke tests for videoink.fetch — no network calls."""

import unittest
from pathlib import Path

from videoink.fetch import FetchResult, _site_slug, fetch


class TestSiteSlug(unittest.TestCase):
    def test_youtube(self):
        self.assertEqual(_site_slug("https://www.youtube.com/watch?v=abc"), "youtube")

    def test_bilibili(self):
        self.assertEqual(_site_slug("https://www.bilibili.com/video/BV123/"), "bilibili")

    def test_vimeo(self):
        self.assertEqual(_site_slug("https://vimeo.com/12345"), "vimeo")

    def test_nonsense_url(self):
        self.assertEqual(_site_slug("not a url"), "download")


class TestFetchArgs(unittest.TestCase):
    def test_empty_url_raises(self):
        with self.assertRaises(ValueError):
            fetch("")

    def test_whitespace_url_raises(self):
        with self.assertRaises(ValueError):
            fetch("   ")


class TestFetchResult(unittest.TestCase):
    def test_dict_round_trip(self):
        r = FetchResult(url="u", mode="audio", out_dir=Path("/tmp"))
        r.audio_path = Path("/tmp/a.m4a")
        r.paths = [Path("/tmp/a.m4a")]
        d = r.as_dict()
        self.assertEqual(d["url"], "u")
        self.assertEqual(d["mode"], "audio")
        self.assertEqual(d["audio_path"], "/tmp/a.m4a")
        self.assertIsNone(d["video_path"])
        self.assertIsNone(d["merged_path"])

    def test_defaults(self):
        r = FetchResult(url="u", mode="separate", out_dir=Path("/tmp"))
        self.assertEqual(r.paths, [])
        self.assertIsNone(r.browser_used)


if __name__ == "__main__":
    unittest.main()
