"""videoink CLI — subcommands that invoke the ``videoink`` library.

Currently implemented:
  * ``probe``  — list available formats (or dump JSON metadata) for a URL.
  * ``fetch``  — download media from a URL.

Planned for v0.1:
  * ``transcribe`` — audio → transcript.
  * ``generate``   — transcript → draft article.
  * ``full``       — end-to-end pipeline (fetch → transcribe → generate → export).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import __version__
from .fetch import FetchResult, fetch, probe_formats, probe_info


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videoink",
        description="Turn any video link into a polished AI article.",
    )
    parser.add_argument("--version", action="version", version=f"videoink {__version__}")

    sub = parser.add_subparsers(dest="command")

    # --- probe ---
    probe_p = sub.add_parser("probe", help="List available formats for a video URL.")
    probe_p.add_argument("url", help="Video page URL (YouTube, Bilibili, or any yt-dlp-supported site).")
    probe_p.add_argument(
        "--browser",
        default="auto",
        help="Browser for --cookies-from-browser. Use auto, none, or a name (chrome, firefox...).",
    )
    probe_p.add_argument(
        "--json",
        action="store_true",
        help="Dump machine-readable extractor JSON instead of the human-readable format table.",
    )

    # --- fetch ---
    fetch_p = sub.add_parser("fetch", help="Download media from a video URL.")
    fetch_p.add_argument("url", help="Video page URL.")
    fetch_p.add_argument(
        "--out-dir",
        type=Path,
        help="Output directory. Defaults to ./.video_cache/<site>/",
    )
    fetch_p.add_argument(
        "--mode",
        choices=("separate", "merged", "audio", "single"),
        default="separate",
        help="Download mode. 'separate' (video+audio tracks) is most reliable for transcription.",
    )
    fetch_p.add_argument("--video-format", help="yt-dlp format expression for the video track.")
    fetch_p.add_argument("--audio-format", help="yt-dlp format expression for the audio track.")
    fetch_p.add_argument("--single-format", help="yt-dlp format expression for merged/single mode.")
    fetch_p.add_argument(
        "--browser",
        default="auto",
        help="Browser for --cookies-from-browser. Use auto, none, or a browser name.",
    )
    fetch_p.add_argument(
        "--summary-json",
        type=Path,
        help="Optional path to write a JSON summary of the download.",
    )

    return parser


def _print_stub_help() -> None:
    print(f"videoink {__version__} — video-to-article pipeline")
    print()
    print("Usage:")
    print("  videoink probe <url>        List available formats for a video URL.")
    print("  videoink fetch <url>        Download media from a video URL.")
    print("  videoink --help             Show full help.")
    print()
    print("Not yet available (v0.1 WIP): transcribe, generate, full.")
    print("See https://github.com/zhujian0409/videoink")


def _handle_probe(args: argparse.Namespace) -> int:
    try:
        if args.json:
            info = probe_info(args.url, browser=args.browser)
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            probe_formats(args.url, browser=args.browser)
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"probe failed: exit {exc.returncode}", file=sys.stderr)
        return exc.returncode


def _handle_fetch(args: argparse.Namespace) -> int:
    try:
        result: FetchResult = fetch(
            args.url,
            out_dir=args.out_dir,
            mode=args.mode,
            video_format=args.video_format,
            audio_format=args.audio_format,
            single_format=args.single_format,
            browser=args.browser,
        )
    except ValueError as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"fetch failed: exit {exc.returncode}", file=sys.stderr)
        return exc.returncode

    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(
            json.dumps(result.as_dict(), ensure_ascii=False, indent=2) + "\n"
        )
        print(f"Wrote summary JSON to {args.summary_json}", file=sys.stderr)

    print(f"\nDownloaded {len(result.paths)} file(s) to {result.out_dir}:", file=sys.stderr)
    for p in result.paths:
        print(f"  {p}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "probe":
        return _handle_probe(args)
    if args.command == "fetch":
        return _handle_fetch(args)

    _print_stub_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
