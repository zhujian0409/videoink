"""Smoke tests for videoink.fetch — no network calls."""

import tempfile
import unittest
from pathlib import Path

from videoink.fetch import FetchResult, _profile_has_cookies, _site_slug, fetch


class TestSiteSlug(unittest.TestCase):
    def test_youtube(self):
        self.assertEqual(_site_slug("https://www.youtube.com/watch?v=abc"), "youtube")

    def test_bilibili(self):
        self.assertEqual(_site_slug("https://www.bilibili.com/video/BV123/"), "bilibili")

    def test_vimeo(self):
        self.assertEqual(_site_slug("https://vimeo.com/12345"), "vimeo")

    def test_nonsense_url(self):
        self.assertEqual(_site_slug("not a url"), "download")

    def test_ipv4_returns_dashed_address(self):
        self.assertEqual(_site_slug("http://10.0.0.1/file.mp4"), "10-0-0-1")

    def test_schemeless_url_recovered(self):
        self.assertEqual(_site_slug("youtube.com/watch?v=abc"), "youtube")

    def test_deep_subdomain_with_new_gtld(self):
        # 4+ label host with a TLD outside the old hard-coded set
        self.assertEqual(_site_slug("https://a.b.c.example.app/x"), "example")

    def test_five_level_subdomain(self):
        self.assertEqual(_site_slug("https://w.x.y.z.example.com/"), "example")

    def test_cc_tld_uk(self):
        self.assertEqual(_site_slug("https://foo.co.uk/path"), "foo")

    def test_single_label_host(self):
        self.assertEqual(_site_slug("http://localhost/x"), "localhost")


class TestProfileHasCookies(unittest.TestCase):
    def test_firefox_profile_dir_without_sqlite(self):
        # Linux server false-positive: ~/.mozilla/firefox exists with an
        # empty 'random.default' subdir but no cookies.sqlite.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "random.default").mkdir()
            self.assertFalse(_profile_has_cookies("firefox", root))

    def test_firefox_with_cookies(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            profile = root / "random.default"
            profile.mkdir()
            (profile / "cookies.sqlite").touch()
            self.assertTrue(_profile_has_cookies("firefox", root))

    def test_firefox_empty_profile_root(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(_profile_has_cookies("firefox", Path(d)))

    def test_firefox_missing_profile_root(self):
        self.assertFalse(
            _profile_has_cookies("firefox", Path("/nonexistent/firefox/xyz"))
        )

    def test_chrome_default_cookies(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "Default").mkdir()
            (root / "Default" / "Cookies").touch()
            self.assertTrue(_profile_has_cookies("chrome", root))

    def test_chrome_network_cookies(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            net = root / "Default" / "Network"
            net.mkdir(parents=True)
            (net / "Cookies").touch()
            self.assertTrue(_profile_has_cookies("chrome", root))

    def test_chrome_profile_without_cookies(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "Default").mkdir()  # exists but no Cookies file
            self.assertFalse(_profile_has_cookies("chrome", root))


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
