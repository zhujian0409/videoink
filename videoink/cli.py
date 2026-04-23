"""videoink CLI — subcommands that invoke the ``videoink`` library.

Subcommands:
  * ``probe``      — list available formats for a URL.
  * ``fetch``      — download media from a URL.
  * ``transcribe`` — audio -> transcript (OpenAI Whisper).
  * ``generate``   — transcript -> Markdown article (LLM).
  * ``full``       — end-to-end pipeline: fetch + transcribe + generate.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from . import __version__
from .fetch import FetchResult, fetch, probe_formats, probe_info
from .generate import GenerateResult, generate_article
from .transcribe import TranscriptResult, transcribe


_DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-6",
    "openrouter": "openai/gpt-4o-mini",
    "ollama": "llama3.2",
}

_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")
_SLUG_MAX_LEN = 128


def _sanitize_slug(s: str) -> str:
    """Make a filesystem-friendly slug from a video id / title.

    Keeps ``[A-Za-z0-9_-]``; runs of anything else collapse to ``-``.
    Trims leading/trailing dashes. Caps length at 128 chars to avoid
    ``ENAMETOOLONG`` when the slug becomes part of a path. Falls back
    to ``"video"`` for an otherwise-empty result.
    """
    s = (s or "").strip()
    s = _SLUG_RE.sub("-", s).strip("-")
    if len(s) > _SLUG_MAX_LEN:
        s = s[:_SLUG_MAX_LEN].rstrip("-_")
    return s or "video"


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
        help="Transcribe an audio file (local faster-whisper or OpenAI Whisper).",
    )
    trans_p.add_argument("audio", type=Path, help="Local audio file.")
    trans_p.add_argument(
        "--engine",
        choices=("openai", "local"),
        default="openai",
        help="openai = Whisper API (needs OPENAI_API_KEY, <=25 MB); "
             "local = faster-whisper (offline, no key, CPU OK).",
    )
    trans_p.add_argument(
        "--model",
        help="Model name. Default: 'whisper-1' for openai, 'base' for local "
             "(local options: tiny/base/small/medium/large-v3).",
    )
    trans_p.add_argument("--language", help="BCP-47 code to bias detection, e.g. 'en'.")
    trans_p.add_argument("--prompt", help="Short text to prime vocabulary / style.")
    trans_p.add_argument(
        "--out-dir",
        type=Path,
        help="Directory for transcript.{json,txt}. Defaults to the audio file's directory.",
    )
    trans_p.add_argument(
        "--base-url",
        help="Override OpenAI API base URL (openai engine only).",
    )

    # --- generate ---
    gen_p = sub.add_parser(
        "generate",
        help="Generate a Markdown article from a transcript JSON.",
    )
    gen_p.add_argument(
        "transcript",
        type=Path,
        help="Path to a transcript JSON produced by `videoink transcribe`.",
    )
    gen_p.add_argument(
        "--provider",
        choices=("openai", "anthropic", "openrouter", "ollama"),
        default="openai",
        help="LLM provider (default: openai).",
    )
    gen_p.add_argument(
        "--model",
        help=f"Model name. Defaults per provider: {_DEFAULT_MODELS}",
    )
    gen_p.add_argument(
        "--style",
        default="default",
        help="Style template name (default / technical / custom in --styles-dir).",
    )
    gen_p.add_argument(
        "--styles-dir",
        type=Path,
        help="Directory to look up style files first (falls back to bundled).",
    )
    gen_p.add_argument("--temperature", type=float, help="Sampling temperature.")
    gen_p.add_argument("--max-tokens", type=int, help="Max output tokens.")
    gen_p.add_argument(
        "--out",
        type=Path,
        help="Output article.md path. Defaults to sibling of the transcript.",
    )

    # --- full ---
    full_p = sub.add_parser(
        "full",
        help="End-to-end: fetch audio + transcribe + generate article.",
    )
    full_p.add_argument("url", help="Video page URL.")
    full_p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Root output directory; a per-video slug subfolder is created (default: ./output).",
    )
    full_p.add_argument(
        "--browser",
        default="auto",
        help="Browser for --cookies-from-browser. Use auto, none, or a browser name.",
    )
    full_p.add_argument("--audio-format", help="yt-dlp audio format expression.")
    full_p.add_argument("--language", help="Transcribe: BCP-47 language code.")
    full_p.add_argument(
        "--engine",
        choices=("openai", "local"),
        default="openai",
        help="Transcribe engine: openai (Whisper API) or local (faster-whisper).",
    )
    full_p.add_argument(
        "--whisper-model",
        help="Model for the transcribe step "
             "(default: whisper-1 for openai, base for local).",
    )
    full_p.add_argument(
        "--provider",
        choices=("openai", "anthropic", "openrouter", "ollama"),
        default="openai",
        help="LLM provider for the generate step (default: openai).",
    )
    full_p.add_argument("--model", help="Override LLM model for generate step.")
    full_p.add_argument(
        "--style",
        default="default",
        help="Article style template (default / technical / custom).",
    )
    full_p.add_argument(
        "--styles-dir",
        type=Path,
        help="Override styles directory for generate step.",
    )
    full_p.add_argument("--temperature", type=float, help="LLM sampling temperature.")
    full_p.add_argument("--max-tokens", type=int, help="LLM max output tokens.")

    return parser


def _print_stub_help() -> None:
    print(f"videoink {__version__} — video-to-article pipeline")
    print()
    print("Usage:")
    print("  videoink probe <url>             List available formats for a video URL.")
    print("  videoink fetch <url>             Download media from a video URL.")
    print("  videoink transcribe <audio>      Transcribe an audio file (Whisper).")
    print("  videoink generate <transcript>   Generate a Markdown article (LLM).")
    print("  videoink full <url>              End-to-end: fetch + transcribe + generate.")
    print("  videoink --help                  Show full help.")
    print()
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
            engine=args.engine,
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


def _get_provider(name: str):
    if name == "openai":
        from .llm import OpenAIProvider
        return OpenAIProvider()
    if name == "anthropic":
        from .llm import AnthropicProvider
        return AnthropicProvider()
    if name == "openrouter":
        from .llm import OpenRouterProvider
        return OpenRouterProvider()
    if name == "ollama":
        from .llm import OllamaProvider
        return OllamaProvider()
    raise ValueError(f"unknown provider: {name}")


def _derive_article_path(transcript_path: Path, explicit_out: Path | None) -> Path:
    if explicit_out is not None:
        return explicit_out
    stem = transcript_path.stem
    if stem.endswith(".transcript"):
        stem = stem[: -len(".transcript")]
    return transcript_path.parent / f"{stem}.article.md"


def _handle_generate(args: argparse.Namespace) -> int:
    try:
        provider = _get_provider(args.provider)
    except ValueError as exc:
        print(f"generate failed: {exc}", file=sys.stderr)
        return 2

    model = args.model or _DEFAULT_MODELS.get(args.provider, "")
    if not model:
        print(f"generate failed: no default model for provider {args.provider!r}", file=sys.stderr)
        return 2

    try:
        result: GenerateResult = generate_article(
            args.transcript,
            provider=provider,
            model=model,
            style=args.style,
            styles_dir=args.styles_dir,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    except (FileNotFoundError, ValueError, ImportError) as exc:
        print(f"generate failed: {exc}", file=sys.stderr)
        return 2

    out_path = _derive_article_path(args.transcript, args.out)
    result.write(out_path)

    print(f"  article.md → {out_path}", file=sys.stderr)
    print(
        f"  provider={result.provider_name}, model={result.model}, "
        f"style={result.style}, chars={len(result.article_md)}",
        file=sys.stderr,
    )
    return 0


def _handle_full(args: argparse.Namespace) -> int:
    url = (args.url or "").strip()
    if not url:
        print("full failed: URL is required", file=sys.stderr)
        return 2

    # 1. Probe metadata (for slug + logging)
    print(f"[full] probe {url}", file=sys.stderr)
    try:
        info = probe_info(url, browser=args.browser)
    except subprocess.CalledProcessError as exc:
        print(f"full failed at probe: exit {exc.returncode}", file=sys.stderr)
        return exc.returncode or 2
    except (ValueError, ImportError) as exc:
        print(f"full failed at probe: {exc}", file=sys.stderr)
        return 2

    video_id = str(info.get("id") or "video")
    title = str(info.get("title") or "untitled")
    duration = info.get("duration")
    slug = _sanitize_slug(video_id)

    out_dir = args.output_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "images").mkdir(exist_ok=True)  # per SKILL.md output contract

    dur_str = f"{duration:.0f}s" if isinstance(duration, (int, float)) else "?"
    print(f"[full] {title}  [{video_id}]  duration={dur_str}", file=sys.stderr)
    print(f"[full] output dir → {out_dir}", file=sys.stderr)

    # 2. Fetch audio
    print("[full] step 1/3: fetch audio", file=sys.stderr)
    try:
        fetch_result = fetch(
            url,
            out_dir=out_dir,
            mode="audio",
            audio_format=args.audio_format,
            browser=args.browser,
        )
    except ValueError as exc:
        print(f"full failed at fetch: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"full failed at fetch: exit {exc.returncode}", file=sys.stderr)
        return exc.returncode or 2

    audio_path = fetch_result.audio_path
    if audio_path is None:
        print("full failed: no audio downloaded", file=sys.stderr)
        return 2

    # 3. Transcribe
    audio_mb = audio_path.stat().st_size / 1024 / 1024
    print(f"[full] step 2/3: transcribe ({audio_mb:.1f} MB)", file=sys.stderr)
    try:
        trans_result = transcribe(
            audio_path,
            engine=args.engine,
            model=args.whisper_model,
            language=args.language,
        )
    except (FileNotFoundError, ValueError, ImportError) as exc:
        print(f"full failed at transcribe: {exc}", file=sys.stderr)
        return 2

    trans_json = out_dir / "transcript.json"
    trans_txt = out_dir / "transcript.txt"
    trans_result.write_json(trans_json)
    trans_result.write_text(trans_txt)

    # 4. Generate
    print(
        f"[full] step 3/3: generate (provider={args.provider}, style={args.style})",
        file=sys.stderr,
    )
    try:
        provider = _get_provider(args.provider)
    except ValueError as exc:
        print(f"full failed: {exc}", file=sys.stderr)
        return 2

    model = args.model or _DEFAULT_MODELS.get(args.provider, "")
    if not model:
        print(f"full failed: no default model for provider {args.provider!r}", file=sys.stderr)
        return 2

    try:
        gen_result = generate_article(
            trans_result,
            provider=provider,
            model=model,
            style=args.style,
            styles_dir=args.styles_dir,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    except (FileNotFoundError, ValueError, ImportError) as exc:
        print(f"full failed at generate: {exc}", file=sys.stderr)
        return 2

    article_path = out_dir / "article.md"
    gen_result.write(article_path)

    # Summary
    print("", file=sys.stderr)
    print("[full] done", file=sys.stderr)
    print(f"  article.md      -> {article_path}", file=sys.stderr)
    print(f"  transcript.json -> {trans_json}", file=sys.stderr)
    print(f"  transcript.txt  -> {trans_txt}", file=sys.stderr)
    print(f"  audio           -> {audio_path}", file=sys.stderr)
    print(
        f"  provider={gen_result.provider_name}, model={gen_result.model}, "
        f"chars={len(gen_result.article_md)}",
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
    if args.command == "generate":
        return _handle_generate(args)
    if args.command == "full":
        return _handle_full(args)

    _print_stub_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
