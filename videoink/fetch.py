"""Video fetching — probe formats and download media from a public URL.

This module wraps ``yt-dlp`` as a subprocess. It handles:

- Locating or bootstrapping yt-dlp.
- Optional browser-cookies fallback for sites that gate content.
- Proxy environment fallback (one retry with proxy env stripped).
- Four download modes: separate / merged / audio / single.

The public API is library-first. The CLI (``videoink/cli.py``) is a thin
wrapper.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import urlparse


# ---- constants -----------------------------------------------------------

DEFAULT_BROWSERS = ("chrome", "brave", "edge", "firefox", "chromium")

PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)

_BROWSER_PROFILE_HINTS: dict[str, dict[str, list[str]]] = {
    "darwin": {
        "chrome": ["~/Library/Application Support/Google/Chrome"],
        "brave": ["~/Library/Application Support/BraveSoftware/Brave-Browser"],
        "edge": ["~/Library/Application Support/Microsoft Edge"],
        "firefox": ["~/Library/Application Support/Firefox/Profiles"],
        "chromium": ["~/Library/Application Support/Chromium"],
    },
    "linux": {
        "chrome": ["~/.config/google-chrome", "~/.var/app/com.google.Chrome/config/google-chrome"],
        "brave": ["~/.config/BraveSoftware/Brave-Browser"],
        "edge": ["~/.config/microsoft-edge"],
        "firefox": ["~/.mozilla/firefox"],
        "chromium": ["~/.config/chromium"],
    },
    "win32": {
        "chrome": ["~/AppData/Local/Google/Chrome/User Data"],
        "brave": ["~/AppData/Local/BraveSoftware/Brave-Browser/User Data"],
        "edge": ["~/AppData/Local/Microsoft/Edge/User Data"],
        "firefox": ["~/AppData/Roaming/Mozilla/Firefox/Profiles"],
        "chromium": ["~/AppData/Local/Chromium/User Data"],
    },
}

DownloadMode = Literal["separate", "merged", "audio", "single"]
BrowserSelection = str  # "auto" | "none" | browser name


# ---- result type ---------------------------------------------------------

@dataclass
class FetchResult:
    url: str
    mode: str
    out_dir: Path
    paths: list[Path] = field(default_factory=list)
    video_path: Path | None = None
    audio_path: Path | None = None
    merged_path: Path | None = None
    browser_used: str | None = None

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "mode": self.mode,
            "out_dir": str(self.out_dir),
            "paths": [str(p) for p in self.paths],
            "video_path": str(self.video_path) if self.video_path else None,
            "audio_path": str(self.audio_path) if self.audio_path else None,
            "merged_path": str(self.merged_path) if self.merged_path else None,
            "browser_used": self.browser_used,
        }


# ---- logging + subprocess helpers ----------------------------------------

def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _run_capture(
    command: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    _log("$ " + " ".join(shlex.quote(part) for part in command))
    return subprocess.run(command, check=False, env=env, text=True, capture_output=True)


def _has_proxy_env(env: dict[str, str]) -> bool:
    return any(env.get(key) for key in PROXY_ENV_KEYS)


def _without_proxy_env(env: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in env.items() if k not in PROXY_ENV_KEYS}


# ---- platform + browser detection ----------------------------------------

def _platform_key() -> str:
    if sys.platform.startswith("darwin"):
        return "darwin"
    if sys.platform.startswith("win"):
        return "win32"
    return "linux"


def _profile_has_cookies(browser: str, profile_root: Path) -> bool:
    """Return True iff ``profile_root`` looks like a usable cookies source.

    Firefox stores cookies at ``<root>/<random>.default/cookies.sqlite``.
    Chromium-family browsers use ``<root>/Default/Cookies`` (newer builds
    may use ``<root>/Default/Network/Cookies`` or numbered profiles).

    Checking by directory existence alone produces false positives on
    Linux servers where ``~/.mozilla/firefox`` exists but is empty.
    """
    if not profile_root.exists():
        return False
    if browser == "firefox":
        try:
            for child in profile_root.iterdir():
                if child.is_dir() and (child / "cookies.sqlite").is_file():
                    return True
        except OSError:
            return False
        return False
    for relative in ("Default/Cookies", "Default/Network/Cookies"):
        if (profile_root / relative).is_file():
            return True
    try:
        for child in profile_root.iterdir():
            if not (child.is_dir() and child.name.startswith("Profile")):
                continue
            for relative in ("Cookies", "Network/Cookies"):
                if (child / relative).is_file():
                    return True
    except OSError:
        return False
    return False


def _available_browsers() -> list[str]:
    hints = _BROWSER_PROFILE_HINTS.get(_platform_key(), {})
    found: list[str] = []
    for browser in DEFAULT_BROWSERS:
        for hint in hints.get(browser, []):
            if _profile_has_cookies(browser, Path(hint).expanduser()):
                found.append(browser)
                break
    return found


def _browser_candidates(selection: BrowserSelection) -> list[str | None]:
    if selection == "none":
        return [None]
    if selection != "auto":
        return [selection]
    found = _available_browsers()
    if not found:
        return [None]
    return [*found, None]


# ---- yt-dlp bootstrap ----------------------------------------------------

def _can_import_yt_dlp(env: dict[str, str] | None = None) -> bool:
    result = subprocess.run(
        [sys.executable, "-c", "import yt_dlp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    return result.returncode == 0


def _prepare_cache_dir(requested: Path) -> Path:
    try:
        requested = requested.resolve()
        requested.mkdir(parents=True, exist_ok=True)
        return requested
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "videoink" / "yt_dlp"
        fallback.mkdir(parents=True, exist_ok=True)
        _log(f"Cache directory not writable; falling back to {fallback}")
        return fallback


def _ensure_yt_dlp(cache_dir: Path | None) -> tuple[list[str], dict[str, str]]:
    """Return a ``[yt-dlp ...]`` invocation prefix and env.

    Prefers a ``yt-dlp`` binary on PATH, then a ``python -m yt_dlp`` import,
    finally a local pip install into ``cache_dir``.
    """
    if shutil.which("yt-dlp"):
        return ["yt-dlp"], os.environ.copy()

    if _can_import_yt_dlp():
        return [sys.executable, "-m", "yt_dlp"], os.environ.copy()

    cache = _prepare_cache_dir(cache_dir or (Path.cwd() / ".videoink_cache" / "yt_dlp"))
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(cache) + (os.pathsep + existing if existing else "")

    if not _can_import_yt_dlp(env):
        install_cmd = [sys.executable, "-m", "pip", "install", "--target", str(cache), "yt-dlp"]
        _log("$ " + " ".join(shlex.quote(p) for p in install_cmd))
        subprocess.run(install_cmd, check=True)

    return [sys.executable, "-m", "yt_dlp"], env


# ---- generic helpers -----------------------------------------------------

_IPV4_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")
_HOST_CHARS_RE = re.compile(r"[a-z0-9.\-:\[\]]+")
_TLD_RE = re.compile(r"[a-z]{2,4}")
_SLUG_CLEAN_RE = re.compile(r"[^a-z0-9]+")


def _site_slug(url: str) -> str:
    """Derive a filesystem-friendly slug from the URL hostname.

    Handles: schemeless URLs (retries with ``https://``), IPv4/IPv6 hosts
    (renders as dashed), and common 2-4-letter ccTLDs (``.uk``, ``.co``,
    ``.me``, ``.app``, ``.dev``, …) in addition to the historical short
    gTLD set. Long new gTLDs (e.g. ``.technology``) are not stripped —
    the slug will be the long TLD itself in that case.
    """
    host = (urlparse(url).hostname or "").lower()
    if not host:
        host = (urlparse(f"https://{url}").hostname or "").lower()
    if not host or not _HOST_CHARS_RE.fullmatch(host):
        return "download"
    if _IPV4_RE.fullmatch(host):
        return host.replace(".", "-")
    if ":" in host:
        return _SLUG_CLEAN_RE.sub("-", host).strip("-") or "download"
    parts = [p for p in host.split(".") if p and p != "www"]
    while len(parts) > 1 and _TLD_RE.fullmatch(parts[-1]):
        parts = parts[:-1]
    if not parts:
        return "download"
    base = _SLUG_CLEAN_RE.sub("-", parts[-1]).strip("-")
    return base or "download"


def _output_template(out_dir: Path, suffix: str) -> str:
    return str(out_dir / f"%(title).150B [%(id)s].{suffix}.%(ext)s")


def _base_command(yt_dlp_cmd: list[str], browser: str | None) -> list[str]:
    cmd = list(yt_dlp_cmd)
    cmd.append("--ignore-config")
    if browser:
        cmd.extend(["--cookies-from-browser", browser])
    return cmd


def _warn_if_direct_media_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    if host.endswith("bilivideo.com") or "upos-" in host or path.endswith((".mp4", ".m4a", ".webm", ".m3u8")):
        _log(
            "URL looks like a direct media link. Prefer the original page URL; "
            "CDN links often expire or return 403."
        )


def _summarize_failure(result: subprocess.CompletedProcess[str]) -> str:
    combined = "\n".join(part for part in (result.stderr, result.stdout) if part).strip()
    if not combined:
        return f"exit code {result.returncode}"
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    return " | ".join(lines[-3:])


def _emit_output(result: subprocess.CompletedProcess[str]) -> None:
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.stdout:
        print(result.stdout, end="")


# ---- execution with browser + proxy fallback -----------------------------

def _execute_with_fallback(
    build_command: Callable[[str | None], list[str]],
    *,
    env: dict[str, str],
    browser_selection: BrowserSelection,
    capture: bool,
) -> tuple[str | None, subprocess.CompletedProcess[str]]:
    """Run ``build_command(browser)`` for each candidate, return first success."""
    attempts = _browser_candidates(browser_selection)
    env_attempts: list[tuple[str, dict[str, str]]] = [("current environment", env)]
    if _has_proxy_env(env):
        env_attempts.append(("proxy-disabled fallback", _without_proxy_env(env)))

    last_result: subprocess.CompletedProcess[str] | None = None
    last_browser: str | None = None
    last_env_label = "current environment"

    for env_idx, (env_label, attempt_env) in enumerate(env_attempts):
        if env_idx > 0:
            _log("Retrying yt-dlp with proxy env variables disabled.")
        for browser in attempts:
            if browser_selection == "auto":
                _log(
                    f"Trying browser cookies from: {browser}"
                    if browser
                    else "Trying without browser cookies."
                )
            result = _run_capture(build_command(browser), env=attempt_env)
            if result.returncode == 0:
                if not capture:
                    _emit_output(result)
                return browser, result

            last_result = result
            last_browser = browser
            last_env_label = env_label

            if browser_selection != "auto":
                if env_idx == len(env_attempts) - 1:
                    if not capture:
                        _emit_output(result)
                    raise subprocess.CalledProcessError(
                        result.returncode,
                        build_command(browser),
                        output=result.stdout,
                        stderr=result.stderr,
                    )
                _log(f"Attempt under {env_label} failed: {_summarize_failure(result)}")
                break

            label = browser or "no cookies"
            _log(f"Attempt with {label} failed under {env_label}: {_summarize_failure(result)}")

    assert last_result is not None
    if not capture:
        _emit_output(last_result)
    _log(f"All yt-dlp attempts failed; last environment was {last_env_label}.")
    raise subprocess.CalledProcessError(
        last_result.returncode,
        build_command(last_browser),
        output=last_result.stdout,
        stderr=last_result.stderr,
    )


# ---- public API ----------------------------------------------------------

def probe_formats(
    url: str,
    *,
    browser: BrowserSelection = "auto",
    cache_dir: Path | None = None,
) -> None:
    """Print yt-dlp's human-readable format table for ``url``. Returns None."""
    _warn_if_direct_media_url(url)
    yt_dlp_cmd, env = _ensure_yt_dlp(cache_dir)

    def build(b: str | None) -> list[str]:
        return _base_command(yt_dlp_cmd, b) + ["-F", url]

    _execute_with_fallback(build, env=env, browser_selection=browser, capture=False)


def probe_info(
    url: str,
    *,
    browser: BrowserSelection = "auto",
    cache_dir: Path | None = None,
) -> dict:
    """Return yt-dlp's extract_info JSON dict (title, duration, formats, etc)."""
    _warn_if_direct_media_url(url)
    yt_dlp_cmd, env = _ensure_yt_dlp(cache_dir)

    def build(b: str | None) -> list[str]:
        return _base_command(yt_dlp_cmd, b) + [
            "--dump-single-json",
            "--skip-download",
            "--no-warnings",
            url,
        ]

    _, result = _execute_with_fallback(build, env=env, browser_selection=browser, capture=True)
    return json.loads(result.stdout)


def _download_one(
    yt_dlp_cmd: list[str],
    env: dict[str, str],
    *,
    browser_selection: BrowserSelection,
    url: str,
    fmt: str,
    out_dir: Path,
    suffix: str,
) -> tuple[str | None, list[Path]]:
    def build(b: str | None) -> list[str]:
        return _base_command(yt_dlp_cmd, b) + [
            "--no-progress",
            "--print",
            "after_move:filepath",
            "-f",
            fmt,
            "-o",
            _output_template(out_dir, suffix),
            url,
        ]

    browser, result = _execute_with_fallback(
        build, env=env, browser_selection=browser_selection, capture=False
    )
    paths = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    return browser, paths


def fetch(
    url: str,
    *,
    out_dir: Path | None = None,
    mode: DownloadMode = "separate",
    video_format: str | None = None,
    audio_format: str | None = None,
    single_format: str | None = None,
    browser: BrowserSelection = "auto",
    cache_dir: Path | None = None,
) -> FetchResult:
    """Download media from ``url`` into ``out_dir``.

    Modes:
      * ``separate`` — download video track and audio track separately
        (most reliable for later transcription / analysis).
      * ``merged``   — download video+audio and merge via ffmpeg.
      * ``audio``    — audio only.
      * ``single``   — a single pre-merged format.
    """
    if not url or not url.strip():
        raise ValueError("A page URL is required.")
    url = url.strip()
    _warn_if_direct_media_url(url)

    if out_dir is None:
        out_dir = Path.cwd() / ".video_cache" / _site_slug(url)
    out_dir.mkdir(parents=True, exist_ok=True)

    yt_dlp_cmd, env = _ensure_yt_dlp(cache_dir)
    result = FetchResult(url=url, mode=mode, out_dir=out_dir)

    if mode == "separate":
        vfmt = video_format or "bestvideo[vcodec*=avc1][ext=mp4]/bestvideo[ext=mp4]/bestvideo"
        afmt = audio_format or "bestaudio[ext=m4a]/bestaudio"
        browser_used, v_paths = _download_one(
            yt_dlp_cmd, env, browser_selection=browser, url=url,
            fmt=vfmt, out_dir=out_dir, suffix="video",
        )
        result.paths.extend(v_paths)
        if v_paths:
            result.video_path = v_paths[-1]
        result.browser_used = browser_used

        browser_used, a_paths = _download_one(
            yt_dlp_cmd, env, browser_selection=browser, url=url,
            fmt=afmt, out_dir=out_dir, suffix="audio",
        )
        result.paths.extend(a_paths)
        if a_paths:
            result.audio_path = a_paths[-1]

    elif mode == "audio":
        afmt = audio_format or "bestaudio[ext=m4a]/bestaudio"
        browser_used, a_paths = _download_one(
            yt_dlp_cmd, env, browser_selection=browser, url=url,
            fmt=afmt, out_dir=out_dir, suffix="audio",
        )
        result.paths.extend(a_paths)
        if a_paths:
            result.audio_path = a_paths[-1]
        result.browser_used = browser_used

    elif mode == "merged":
        has_ffmpeg = shutil.which("ffmpeg") is not None
        if has_ffmpeg:
            mfmt = single_format or "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b"
            suffix = "merged"
        else:
            _log("ffmpeg not found; falling back to best single file.")
            mfmt = single_format or "best[ext=mp4]/best"
            suffix = "single"
        browser_used, m_paths = _download_one(
            yt_dlp_cmd, env, browser_selection=browser, url=url,
            fmt=mfmt, out_dir=out_dir, suffix=suffix,
        )
        result.paths.extend(m_paths)
        if m_paths:
            result.merged_path = m_paths[-1]
        result.browser_used = browser_used

    else:  # single
        sfmt = single_format or "best[ext=mp4]/best"
        browser_used, s_paths = _download_one(
            yt_dlp_cmd, env, browser_selection=browser, url=url,
            fmt=sfmt, out_dir=out_dir, suffix="single",
        )
        result.paths.extend(s_paths)
        if s_paths:
            result.merged_path = s_paths[-1]
        result.browser_used = browser_used

    return result
