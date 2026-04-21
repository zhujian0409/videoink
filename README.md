# videoink

**Languages:** English | [中文](./README.zh-CN.md)

> Turn any video link into a polished Markdown article. **Skill-native inside Claude Code (zero API cost)** — or a **standalone CLI** with your own keys.

**Status:** v0.1 alpha. End-to-end works. Not yet on PyPI — install from git (see below).

Paste a YouTube, Bilibili, or any yt-dlp-supported video URL. `videoink` fetches the audio, transcribes it (locally or via OpenAI Whisper), and produces a publishable Markdown article plus a local bundle. You publish it wherever you want — Substack, Ghost, dev.to, Medium, Obsidian, your own static site.

## Two ways to run it

| Mode | Transcribe step | Article step | External API cost |
|---|---|---|---|
| **Claude Code skill** *(recommended)* | local `faster-whisper` | Claude Code itself writes it | **$0** |
| Standalone CLI | local `faster-whisper` or OpenAI Whisper | OpenAI / Anthropic API | Pay per run (typ. <$0.10) |

The skill-native mode is the design point. Everything stays on your machine; no credentials ever leave it.

## Why

Closed SaaS like Cast Magic and Podsqueeze do something similar, but:

- They lock you into their LLM backend and pricing.
- Your transcripts and drafts live in their cloud.
- You can't run them on Ollama / air-gapped infra.

`videoink` is one pip-installable Python package plus a Claude Code skill. Bring your own keys for OpenAI / Anthropic **only if** you want the CLI mode; Claude Code users need no key at all.

## Quickstart — Claude Code skill, zero API

```bash
# Install with the local-whisper extra. No API key anywhere.
pip install 'git+https://github.com/zhujian0409/videoink.git#egg=videoink[local]'
```

Then in Claude Code, paste a video URL and ask for an article. The skill will:

1. download the audio via `yt-dlp`
2. transcribe it offline with `faster-whisper` (first run downloads the ~145 MB base model from Hugging Face)
3. have Claude Code itself read the transcript and write `article.md`

All produced under `./output/<video-id>/`.

## Quickstart — standalone CLI, with an API key

```bash
# Install both openai and local extras (local still used for transcribe by default)
pip install 'git+https://github.com/zhujian0409/videoink.git#egg=videoink[openai,local]'

# One provider key
export OPENAI_API_KEY=sk-...           # or ANTHROPIC_API_KEY=sk-ant-...

# Run the full pipeline
videoink full https://www.youtube.com/watch?v=<id> --engine local
```

Drop `--engine local` to use OpenAI Whisper instead; add `--provider anthropic` to drive the generate step through Claude.

## What you get

```
./output/<video-id>/
    article.md                  # publishable Markdown
    transcript.json             # full Whisper output (segments, timing, language)
    transcript.txt              # plain-text transcript
    images/                     # empty in v0.1; reserved for v0.2
    <title> [<id>].audio.m4a    # the audio we transcribed
```

Open `article.md` in any Markdown editor. Publish from there.

## Prerequisites

- Python 3.10+
- `ffmpeg` on PATH (used by yt-dlp)
- **Claude Code skill mode**: nothing else (first run downloads the `faster-whisper` base model, ~145 MB)
- **Standalone CLI mode**: one of `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`

## Subcommands

| | What it does |
|---|---|
| `videoink probe <url>` | List all downloadable formats / dump extractor JSON |
| `videoink fetch <url> --mode audio` | Download audio only |
| `videoink transcribe <audio> --engine local` | Offline faster-whisper → `transcript.{json,txt}` |
| `videoink transcribe <audio> --engine openai` | OpenAI Whisper API (25 MB cap) |
| `videoink generate <transcript.json>` | Transcript + style → `article.md` (requires LLM key; **not** used in Claude Code mode) |
| `videoink full <url>` | All four steps (for CLI mode) |

All subcommands accept `--help`.

## Styles

Two built-in styles ship as package data:

- `default` — neutral blog / newsletter voice
- `technical` — engineering-audience voice

Bring your own:

```bash
videoink full <url> --style mystyle --styles-dir ./my-styles/
# expects ./my-styles/mystyle.md
```

In Claude Code mode, just tell the assistant which style file to follow.

## Claude Code skill

The [`SKILL.md`](./SKILL.md) at the repo root is the skill definition Claude Code reads. It encodes the 3-step skill-native workflow (fetch → local transcribe → assistant writes) and an explicit "do NOT call `videoink generate` inside Claude Code" rule so the skill never opens an unneeded LLM billing channel.

## Roadmap

See [`ROADMAP.md`](./ROADMAP.md). Short version:

- **v0.1** ✓ — 5 CLI subcommands, local + OpenAI transcribe engines, OpenAI + Anthropic LLM providers, Claude Code skill, zero-API skill-native mode.
- **v0.2** — OpenRouter + Ollama providers, multi-model judge loop, Bilibili first-class, auto-chunk >25 MB audio, web image sourcing.
- **v0.3+** — Codex / Cursor / other agent skill adapters, optional HTTP API.

## Background

This repo started from a working-but-personal pipeline the author ran daily for three weeks (news video → long-form article). The public release strips platform-specific publishing code, uses English-by-default prompts, makes the LLM backend pluggable, and produces plain Markdown you publish yourself.

## Contributing

`ROADMAP.md` has a `v0.2 backlog` section with concrete, contained tasks. PRs welcome.

## License

[MIT](./LICENSE)
