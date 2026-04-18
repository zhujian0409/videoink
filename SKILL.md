---
name: videoink
description: Use when the user provides a public video URL (YouTube, Bilibili, or any yt-dlp-supported platform) and wants to turn it into a polished Markdown article with embedded images. Orchestrates the full video-to-article pipeline - fetch media, transcribe, draft, polish with the user's chosen LLM (OpenAI, Anthropic, OpenRouter, or Ollama), and export Markdown plus an image directory ready for publishing.
---

# videoink — video-to-article skill

**Status:** v0.1 alpha. This skill file is a stub; the full workflow
is under active development. Track progress in
[README.md](./README.md).

## Trigger

Invoke this skill when the user:

- Supplies a URL from YouTube, Bilibili, or any platform yt-dlp
  supports, and asks for an article / blog post / newsletter based
  on it.
- Says things like "summarize this video as a blog post", "turn
  this podcast into a newsletter", or "write an article from this
  video".

## Prerequisites

- `videoink` Python package installed (`pip install videoink`).
- `ffmpeg` on the system PATH.
- At least one LLM provider configured via env var:
  `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`,
  or `OLLAMA_HOST`.

## Output contract

Running the full pipeline produces, per video URL:

- `./output/<slug>/article.md` — publishable Markdown
- `./output/<slug>/images/` — referenced local images
- `./output/<slug>/transcript.json` — raw ASR output (for debugging)

The assistant should hand the user these paths and avoid uploading
or publishing the article anywhere. `videoink` is intentionally an
**export-to-local-files** tool; choice of publication channel is
left to the user.
