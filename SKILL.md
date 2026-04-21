---
name: videoink
description: Use when the user provides a public video URL (YouTube, Bilibili, or any yt-dlp-supported platform) and wants to turn it into a polished Markdown article. Orchestrates the end-to-end video-to-article pipeline through the `videoink` CLI - fetch audio, transcribe with OpenAI Whisper, draft an article with the user's chosen LLM (OpenAI or Anthropic), and export Markdown plus a bundle directory ready for publishing. The skill does not publish anywhere; it leaves article.md on disk.
---

# videoink — video-to-article skill

## When to invoke

The user supplies a public video URL AND asks for textual output derived from the video. Typical phrasings:

- "Summarize this video as a blog post"
- "Turn this podcast into a newsletter"
- "Write an article from this YouTube video"
- "把这个视频/B站链接写成一篇文章"
- "Give me a transcript of this video" (→ run partial pipeline, see below)

## Do NOT invoke for

- Questions about the video that can be answered from metadata alone.
- Requests to *download* the video as a file (→ `videoink fetch` directly, or plain `yt-dlp`).
- Editing / polishing an article the user has already pasted in.
- Requests to *publish* the result somewhere (this skill stops at Markdown; the user picks the channel).

## Prerequisites

Verify before running. If any is missing, report it and stop — do not attempt to install anything for the user.

- `videoink` Python package installed: `pip install 'videoink[openai,anthropic]'`.
- `ffmpeg` on the system PATH (required by yt-dlp audio extraction).
- At least one LLM provider key in the environment:
  - `OPENAI_API_KEY` (default provider), or
  - `ANTHROPIC_API_KEY`.

## Default workflow — one command

```
videoink full <url>
```

That single call runs `probe → fetch audio → transcribe → generate` and writes:

```
./output/<video-id>/
    article.md              ← publishable Markdown
    transcript.json         ← raw Whisper output (segments, timing, language)
    transcript.txt          ← plain-text transcript
    images/                 ← empty in v0.1; reserved for v0.2
    <title> [<id>].audio.m4a
```

Hand the user the absolute path to `article.md`. Let them open or publish it.

## Mapping user intent to flags

| User signal | Flag |
|---|---|
| "Developer-audience / technical tone" | `--style technical` |
| "Use Claude / Anthropic" | `--provider anthropic` |
| "The speaker is in Mandarin / Japanese / ..." | `--language zh` / `--language ja` / ... |
| "Save it into project X" | `--output-dir ./projects/X/output` |
| "Keep it short / more creative" | `--max-tokens 2000` / `--temperature 0.7` |
| "I already wrote custom style rules" | `--style myname --styles-dir ./my-styles/` |

If the user does not specify: defaults are OpenAI + `gpt-4o` + style `default`.

## Partial pipelines

Sometimes the user does not want the whole pipeline. Use the step-specific subcommand:

| User wants only... | Command |
|---|---|
| The transcript | `videoink fetch <url> --mode audio && videoink transcribe <audio>` |
| A list of available video/audio formats | `videoink probe <url>` |
| An article from a transcript they already have | `videoink generate <transcript.json>` |

## Error recovery

**Audio file larger than 25 MB** (Whisper API hard limit). Pre-split:

```bash
ffmpeg -i audio.m4a -f segment -segment_time 600 -c copy chunk%d.m4a
# then transcribe each chunk; concatenate the 'text' fields
```

Automatic chunking is planned for v0.2.

**yt-dlp format extraction fails or returns an unexpected codec**. Run:

```bash
videoink probe <url>
```

Pick a format ID and re-run with `--audio-format <id>`.

**Missing API key / SDK not installed**. The CLI prints a message naming the env var or pip extra; surface it to the user verbatim rather than guessing.

## What this skill does NOT do (v0.1 scope)

- Does not upload, publish, or post the article.
- Does not fetch or embed images from the web (v0.2).
- Does not auto-split audio longer than Whisper's 25 MB limit (v0.2).
- Does not authenticate against Bilibili 1080P+ / member content (v0.2).
- Does not invent facts not supported by the transcript; the built-in styles rule this out explicitly.
