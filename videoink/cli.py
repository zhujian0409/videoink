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
from .transcribe import TranscriptResult, transcribe


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

    # --- transcribe ---
    trans_p = sub.add_parser(
        "transcribe",
        help="Transcribe an audio file using OpenAI Whisper API.",
    )
    trans_p.add_argument("audio", type=Path, help="Local audio file (<= 25 MB).")
    trans_p.add_argument("--model", default="whisper-1", help="Whisper model name.")
    trans_p.add_argument("--language", help="BCP-47 code to bias detection, e.g. 'en'.")
    trans_p.add_argument("--prompt", help="Short text to prime vocabulary / style.")
    trans_p.add_argument(
        "--out-dir",
        type=Path,
        help="Directory for transcript.{json,txt}. Defaults to the audio file's directory.",
    )
    trans_p.add_argument(
        "--base-url",
        help="Override OpenAI API base URL (for OpenAI-compatible proxies).",
    )

    return parser


def _print_stub_help() -> None:
    print(f"videoink {__version__} — video-to-article pipeline")
    print()
    print("Usage:")
    print("  videoink probe <url>          List available formats for a video URL.")
    print("  videoink fetch <url>          Download media from a video URL.")
    print("  videoink transcribe <audio>   Transcribe an audio file (Whisper).")
    print("  videoink --help               Show full help.")
    print()
    print("Not yet available (v0.1 WIP): generate, full.")
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


def _handle_transcribe(args: argparse.Namespace) -> int:
    try:
        result: TranscriptResult = transcribe(
            args.audio,
            model=args.model,
            language=args.language,
            prompt=args.prompt,
            base_url=args.base_url,
        )
    except (FileNotFoundError, ValueError, ImportError) as exc:
        print(f"transcribe failed: {exc}", file=sys.stderr)
        return 2

    out_dir = args.out_dir or args.audio.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    base = args.audio.stem
    json_path = out_dir / f"{base}.transcript.json"
    txt_path = out_dir / f"{base}.transcript.txt"
    result.write_json(json_path)
    result.write_text(txt_path)

    dur = f"{result.duration:.1f}s" if result.duration is not None else "?"
    print(f"  transcript.json → {json_path}", file=sys.stderr)
    print(f"  transcript.txt  → {txt_path}", file=sys.stderr)
    print(
        f"  language: {result.language}, duration: {dur}, "
        f"segments: {len(result.segments)}",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "probe":
        return _handle_probe(args)
    if args.command == "fetch":
        return _handle_fetch(args)
    if args.command == "transcribe":
        return _handle_transcribe(args)

    _print_stub_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
