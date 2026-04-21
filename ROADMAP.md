# videoink roadmap

Tracking what's done, what's next, and what's parked.
See `README.md` for the project pitch.

---

## v0.1 (current, in progress)

First pip-installable alpha. Target release: after the items in
`## Remaining for v0.1` ship.

### Done

- CLI subcommands: `probe`, `fetch`, `transcribe`, `generate`, `full`
- Core modules (~2.5 K lines, all stdlib + yt-dlp + optional openai / anthropic):
  - `videoink/fetch.py` — yt-dlp wrapper, 4 download modes, browser-cookie + proxy fallback
  - `videoink/transcribe.py` — OpenAI Whisper (25 MB cap, ffmpeg pre-split hint)
  - `videoink/generate.py` — transcript + style + LLM provider → Markdown article
  - `videoink/llm/{openai,anthropic}.py` — two providers, lazy SDK import
  - `_handle_full` — end-to-end orchestrator producing `./output/<slug>/{article.md,transcript.{json,txt},images/}`
- Built-in styles `default` + `technical`, bundled as `package-data`
- 62 unit tests, **all zero-network**, 13 ms full suite

### Remaining for v0.1

- [ ] `SKILL.md` — flesh out the Claude Code skill with concrete trigger → call sequence (currently a stub)
- [ ] Real end-to-end smoke test against a public YouTube video with a real `OPENAI_API_KEY` (done locally, not in CI)
- [ ] README polish + 30-second asciinema/gif demo
- [ ] Switch repo from **private → public** (when all above pass)

---

## v0.2 backlog

Grouped by theme. Items here are accepted as "we want this" but not scheduled.

### Correctness / UX (from thorough-check observations)

- **N1** `videoink/generate.py` — `_load_transcript`: reject non-dict JSON with a clear `ValueError` instead of `AttributeError` on `list.get` (e.g. user passes `["a","b"]` as transcript).
- **N2** `videoink/generate.py` — `_build_messages`: replace literal `--- STYLE RULES ---` / `--- TRANSCRIPT ---` delimiters with UUID-scoped XML-style tags to close the prompt-injection vector (transcript content that contains the delimiter can influence the LLM's system prompt).
- **N3** `videoink/generate.py` — `generate_article`: guard `.strip()` behind `str(article or "")` so a misbehaving custom provider (returning `None` / non-str) doesn't produce a cryptic `AttributeError`.
- **S1** `videoink/fetch.py` — `_site_slug`: improve edge cases. IP URLs currently return `"10"` for `10.0.0.1`; 4+ level subdomains return the wrong segment; URLs without `https://` scheme fall back to `"download"`. Consider deriving from full host with `-` replacement.
- **S2** `videoink/fetch.py` — `_available_browsers`: detect browsers by the presence of an actual `cookies.sqlite`, not just the profile directory. Fixes the Linux false-positive where Firefox is "found" but yt-dlp then fails to read cookies.
- **S3** `videoink/transcribe.py` — automatic chunking for audio > 25 MB (Whisper API limit). Today users have to pre-split with ffmpeg.
- **S4** `videoink/cli.py` — `_sanitize_slug`: cap output length at 128 chars to avoid `ENAMETOOLONG` on extreme inputs (real YouTube/Bilibili IDs never trigger this, but future user-supplied `--slug` could).

### New features

- `OpenRouterProvider`, `OllamaProvider` (unify the v0.2 provider set to four)
- Multi-model polish/judge loop: generate N variants, have another model pick the best
- Bilibili first-class support: cookie handling, 1080P+, anti-leech
- Keyframe-based image insertion + web-image sourcing (exists in the private Codex skill; needs generalising)
- More bundled styles: `newsletter`, `summary`, `interview`

### Dev infrastructure

- GitHub Actions: `pytest` on push + release workflow
- Real CI smoke test against a short public YouTube video
- `pre-commit` hooks: `ruff` format + lint

---

## v0.3+ (ideas, no commitment)

- Codex / Gemini / Cursor / other agent skill front-ends — thin `SKILL.md` variants that all call the same `videoink` Python API
- Optional HTTP API for team deployments
- Pro SaaS: hosted instance, quota-based, zero-setup
- Structured knowledge extraction from transcripts (entities, timeline, citations)
