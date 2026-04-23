# videoink roadmap

Tracking what's done, what's next, and what's parked.
See `README.md` for the project pitch.

---

## v0.1 (shipped 2026-04-21)

First pip-installable alpha. Tagged `v0.1.0a0` on GitHub.

### Done

- CLI subcommands: `probe`, `fetch`, `transcribe`, `generate`, `full`
- Core modules (~2.5 K lines, all stdlib + yt-dlp + optional openai / anthropic / faster-whisper):
  - `videoink/fetch.py` — yt-dlp wrapper, 4 download modes, browser-cookie + proxy fallback
  - `videoink/transcribe.py` — **two engines**: `local` (offline faster-whisper, CPU-friendly, no API key) and `openai` (Whisper API, 25 MB cap)
  - `videoink/generate.py` — transcript + style + LLM provider → Markdown article (standalone CLI path)
  - `videoink/llm/{openai,anthropic}.py` — two providers, lazy SDK import
  - `_handle_full` — end-to-end orchestrator producing `./output/<slug>/{article.md,transcript.{json,txt},images/}`
- **Claude Code skill** (`SKILL.md`) with skill-native 3-step workflow: `fetch → transcribe --engine local → assistant writes article.md`. **Zero external API cost** in Claude Code.
- Built-in styles `default` + `technical`, bundled as `package-data`.
- 62 unit tests, **all zero-network**, 13 ms full suite.
- Real end-to-end verified: Fireship "CSS in 100 Seconds" (140 s) → Markdown article, $0 external spend.
- README + README.zh-CN with two-mode Quickstart; `docs/providers.md` aligned with shipped providers.

### Carried over to v0.2 / not release-blocking

- Short demo (asciinema or Claude Code screen recording → gif) at README top.
- (Optional) PyPI release — `python -m build && twine upload`.

---

## v0.2 (shipped 2026-04-22)

Correctness / UX hardening pass — all items from the v0.1 `thorough-check`
observation list. 92 unit tests, all zero-network. No behaviour change for
the default happy path; edge cases now fail clearly or succeed where they
previously broke.

### Done — correctness / UX hardening

- **N1** `generate._load_transcript` raises `ValueError` for non-dict JSON.
- **N2** `generate._build_messages` uses per-call UUID-scoped XML tags for style/transcript delimiters — closes the prompt-injection vector.
- **N3** `generate.generate_article` coerces provider result to `str` before `.strip()` (guards `None` / non-str).
- **S1** `fetch._site_slug` handles IPv4/IPv6 hosts, schemeless URLs, and common 2-4-letter ccTLDs beyond the original hard-coded set. (Long new gTLDs like `.technology` are a known limitation.)
- **S2** `fetch._available_browsers` requires an actual cookies DB (`cookies.sqlite` for Firefox; `Default/Cookies` or `Default/Network/Cookies` for Chromium family) — fixes the Linux-server false-positive.
- **S3** `transcribe` auto-chunks oversized audio via ffmpeg `-f segment -c copy` for the openai engine, stitching per-chunk segment timestamps back onto the original timeline.
- **S4** `cli._sanitize_slug` caps output length at 128 chars to prevent `ENAMETOOLONG`.

## v0.3 (current — 2026-04-23)

Provider set widened and CI on. 110 unit tests, all zero-network, matrix
across Python 3.10 / 3.11 / 3.12 on GitHub Actions.

### Done

- **OpenRouterProvider**: one gateway, many models; OpenAI-compatible
  endpoint at `openrouter.ai/api/v1`. Supports optional `HTTP-Referer` /
  `X-Title` attribution headers via `OPENROUTER_HTTP_REFERER` /
  `OPENROUTER_X_TITLE`.
- **OllamaProvider**: fully local inference against `localhost:11434/v1`
  (or wherever `OLLAMA_HOST` points — bare host:port or full URL). No
  API key required.
- **CLI wiring**: `--provider openrouter|ollama` on both `generate` and
  `full`, with sensible per-provider defaults (`openai/gpt-4o-mini`,
  `llama3.2`).
- **3 new bundled styles**: `newsletter` (conversational, hook-driven),
  `summary` (tight ~300-500 word recap), `interview` (preserves verbatim
  quotes for podcasts / talking-heads).
- **GitHub Actions CI**: `pytest -q` on push to main and on PRs, matrix
  on Python 3.10 / 3.11 / 3.12. CI + license badges on README.

## v0.4 backlog

### New features

- Multi-model polish/judge loop: generate N variants, have another model pick the best
- Bilibili first-class support: cookie handling, 1080P+, anti-leech
- Keyframe-based image insertion + web-image sourcing (exists in the private Codex skill; needs generalising)

### Dev infrastructure

- Real CI smoke test against a short public YouTube video
- `pre-commit` hooks: `ruff` format + lint
- Release workflow on tag push (build sdist/wheel; optionally publish to PyPI)

---

## v0.5+ (ideas, no commitment)

- Codex / Gemini / Cursor / other agent skill front-ends — thin `SKILL.md` variants that all call the same `videoink` Python API
- Optional HTTP API for team deployments
- Pro SaaS: hosted instance, quota-based, zero-setup
- Structured knowledge extraction from transcripts (entities, timeline, citations)
