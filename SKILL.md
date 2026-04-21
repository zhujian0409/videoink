---
name: videoink
description: Use when the user provides a public video URL (YouTube, Bilibili, or any yt-dlp-supported platform) and wants to turn it into a polished Markdown article. In Claude Code the skill runs offline - local faster-whisper for transcription, Claude Code itself writes the article (no external LLM API). Fetch + transcribe are local commands; generation is done by you (the assistant) reading the transcript directly.
---

# videoink — video-to-article skill (skill-native, zero API cost)

## When to invoke

The user supplies a public video URL AND asks for textual output derived from the video. Typical phrasings:

- "Summarize this video as a blog post"
- "Turn this podcast into a newsletter"
- "Write an article from this YouTube video"
- "把这个视频/B站链接写成一篇文章"
- "Give me a transcript of this video" (→ run only steps 1-2 below)

## Do NOT invoke for

- Questions about the video that can be answered from metadata alone.
- Requests to *download* the video as a file (→ `videoink fetch` directly, or plain `yt-dlp`).
- Editing / polishing an article the user has already pasted in.
- Requests to *publish* the result somewhere (this skill stops at Markdown on disk).

## Prerequisites

- `videoink` installed with local-whisper extra: `pip install 'videoink[local]'`.
- `ffmpeg` on PATH (used by yt-dlp).
- **No LLM API key required** in skill-native mode.

## Default workflow (skill-native, 3 steps)

```
1. videoink fetch --mode audio <url>                    # downloads audio only
2. videoink transcribe --engine local <audio_file>      # offline faster-whisper
3. YOU (the assistant) read the transcript.json and write article.md
```

### Step 1 — fetch audio

```bash
videoink fetch --mode audio <url> --out-dir ./output/<video-id>/
```

The slug (`<video-id>`) comes from the video's canonical id; pick it from `videoink probe <url> --json` if you want control, else let `videoink full` derive it.

### Step 2 — transcribe locally

```bash
videoink transcribe --engine local ./output/<slug>/*.audio.m4a
```

Produces `*.transcript.json` (full segments + timestamps) and `*.transcript.txt`. Offline. No API key.

For a non-English source: add `--language zh` / `--language ja` / etc.

### Step 3 — YOU write the article

Don't call `videoink generate`. **Instead, do it yourself**:

1. Read the style rules by opening `videoink/styles/<style>.md` (from the installed package). `default` is the neutral blog / newsletter voice. Pick `technical` if the user asks for a dev-blog tone.
2. Read the transcript file (`*.transcript.json` or the `.txt`).
3. Write the article **directly into** `./output/<slug>/article.md`, following the style rules strictly.
4. Hand the user the absolute path to `article.md`.

**Why you, not `videoink generate`**: in Claude Code you ARE the LLM. Calling `videoink generate` would open a second HTTP billing channel (OpenAI/Anthropic) that the user has to fund separately. Writing it yourself is faster, cheaper, and uses the model the user already has.

## Output contract

```
./output/<slug>/
    article.md                   ← YOU wrote this
    *.transcript.json            ← faster-whisper output
    *.transcript.txt
    *.audio.m4a
    images/                      ← empty in v0.1
```

Hand the user the absolute path to `article.md`. Do not publish anywhere.

## Mapping user intent to flags / style

| User signal | Action |
|---|---|
| "Developer-audience / technical tone" | read `videoink/styles/technical.md` |
| "The speaker is in Mandarin / Japanese / ..." | `videoink transcribe ... --language zh` |
| "Save into project X" | `--out-dir ./projects/X/output/<slug>` |
| "Use a bigger/smaller Whisper" | `videoink transcribe ... --model small` (or `tiny`/`medium`/`large-v3`) |

Default: local-engine `base` model, `default` style, output under `./output/<slug>/`.

## Error recovery

**faster-whisper not installed**: the command prints `pip install 'videoink[local]'`. Surface it to the user verbatim.

**yt-dlp format extraction fails**: run `videoink probe <url>`, inspect formats, re-run with an explicit `--audio-format <id>`.

## Standalone / non-skill usage (for reference)

When NOT running inside Claude Code (e.g. cron, CI, headless server), the skill-native flow doesn't apply — there's no LLM "you" to write the article. In those cases use:

- `videoink full <url> --engine local --provider openai --model gpt-4o` — drives the generate step via an external LLM (needs `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`).
- `videoink generate <transcript.json>` — same, but standalone.

These still exist; they're just the wrong default inside Claude Code.

## What this skill does NOT do (v0.1 scope)

- Does not upload, publish, or post the article.
- Does not fetch or embed images from the web (v0.2).
- Does not authenticate against Bilibili 1080P+ / member content (v0.2).
- Does not invent facts unsupported by the transcript; the built-in styles rule this out explicitly.
