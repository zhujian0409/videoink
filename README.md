# videoink

> Turn any video link into a polished AI article. Markdown + images, multi-LLM.

**Status:** v0.1 alpha. End-to-end works locally with an OpenAI or Anthropic API key. Not yet on PyPI — install from git (see below).

Paste a YouTube, Bilibili, or any yt-dlp-supported video URL. `videoink` fetches the audio, transcribes it with OpenAI Whisper, drafts an article with the LLM of your choice, and writes a publishable Markdown file plus a local bundle. You publish it wherever you want — Substack, Ghost, dev.to, Medium, Obsidian, your own static site, etc.

## Why

Closed SaaS like Cast Magic and Podsqueeze do something similar, but:

- They lock you into their LLM backend and pricing.
- Your transcripts and drafts live in their cloud.
- You can't run them on Ollama or air-gapped infra.

`videoink` is one pip-installable Python package plus a Claude Code skill. Bring your own keys for **OpenAI / Anthropic** (v0.1); **OpenRouter / Ollama** are planned for v0.2. Your video, your transcripts, your drafts — all local files.

## Quickstart

```bash
# 1. Install (PyPI release pending — install from git for now)
pip install 'git+https://github.com/zhujian0409/videoink.git#egg=videoink[openai,anthropic]'

# 2. One key is enough
export OPENAI_API_KEY=sk-...            # or ANTHROPIC_API_KEY=sk-ant-...

# 3. Run
videoink full https://www.youtube.com/watch?v=<id>
```

### What you get

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
- `ffmpeg` on the system PATH (used by yt-dlp for audio extraction)
- One LLM provider key: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`

## Subcommands

| | What it does |
|---|---|
| `videoink probe <url>` | List all downloadable formats / dump extractor JSON |
| `videoink fetch <url> --mode audio` | Download audio only (default is `separate` video+audio) |
| `videoink transcribe <audio.m4a>` | Audio → `transcript.json` + `transcript.txt` |
| `videoink generate <transcript.json>` | Transcript + style → `article.md` |
| `videoink full <url>` | All four steps in one call (the common case) |

All subcommands accept `--help`.

## Styles

Two built-in styles ship as package data:

- `--style default` — neutral blog / newsletter voice (default)
- `--style technical` — engineering-audience voice

Bring your own:

```bash
videoink full <url> --style mystyle --styles-dir ./my-styles/
# expects ./my-styles/mystyle.md
```

## Claude Code skill

This repo is also a [Claude Code skill](https://docs.claude.com/en/docs/claude-code/skills). Drop it into your skills directory and Claude will invoke the pipeline whenever you paste a video URL and ask for an article. See [`SKILL.md`](./SKILL.md).

## Roadmap

See [`ROADMAP.md`](./ROADMAP.md). Short version:

- **v0.1** ✓ — 5 CLI subcommands, OpenAI + Anthropic providers, Markdown export, Claude Code skill.
- **v0.2** — OpenRouter + Ollama, multi-model judge loop, Bilibili first-class, auto-chunk >25 MB audio, web image sourcing.
- **v0.3+** — Codex / Cursor / other agent skill adapters, optional HTTP API.

## Background

This repo started from a working-but-personal pipeline the author ran daily for three weeks (news video → long-form article). The public release strips platform-specific publishing code, uses English-by-default prompts, makes the LLM backend pluggable, and produces plain Markdown you publish yourself.

## Contributing

`ROADMAP.md` has a `v0.2 backlog` section with concrete, contained tasks. PRs welcome.

## License

[MIT](./LICENSE)
