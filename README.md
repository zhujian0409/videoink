# videoink

> Turn any video link into a polished AI article. Markdown + images, multi-LLM.

**Status:** v0.1 alpha — under active development. Not yet usable.

Paste a YouTube, Bilibili, or any yt-dlp-supported video URL. `videoink`
fetches the media, transcribes it, drafts an article, polishes it with
the LLM of your choice, and exports a ready-to-publish Markdown file
plus a local image directory. You publish it wherever you want —
Substack, Ghost, dev.to, Medium, Obsidian, your own static site, etc.

## Why

Closed SaaS like Cast Magic and Podsqueeze do something similar, but:

- They lock you into their LLM backend and pricing.
- Your transcripts and drafts live in their cloud.
- You can't run them on Ollama / air-gapped infra.

`videoink` is a single pip-installable Python package plus a Claude
Code skill. Bring your own keys for **OpenAI / Anthropic / OpenRouter
/ Ollama**. Your video, your transcripts, your drafts — all local
files.

## Quickstart (coming in v0.1)

```bash
pip install videoink
export OPENAI_API_KEY=sk-...      # or ANTHROPIC_API_KEY
videoink full https://www.youtube.com/watch?v=<id>

# output:
#   ./output/<slug>/article.md
#   ./output/<slug>/images/
```

## Roadmap

- **v0.1** *(in progress)* — OpenAI + Anthropic providers, Markdown
  export, Claude Code skill integration, 2 built-in styles
  (`default`, `technical`).
- **v0.2** — OpenRouter + Ollama providers, multi-model polish-judge
  loop, Bilibili first-class support, more styles.
- **v0.3+** — optional Codex skill, keyframe-based image insertion,
  web-image sourcing.

## Background

This repo was seeded from a working-but-personal pipeline the author
ran daily for three weeks (Chinese news video → WeChat article). The
public release is being generalized: WeChat-specific publishing code
is stripped, prompts are English-by-default, LLM backends are
pluggable, and the output is plain Markdown you publish wherever
you like.

## License

[MIT](./LICENSE)
