# LLM providers

`videoink` supports multiple LLM backends for the `generate` / `full`
subcommands (the **standalone CLI path**). Inside Claude Code, the
skill-native workflow skips `videoink generate` entirely and lets
Claude Code itself write the article — no provider / key needed there.

## Shipping in v0.1

| Provider  | Env var              | Status |
|-----------|----------------------|--------|
| OpenAI    | `OPENAI_API_KEY`     | ✅ shipped |
| Anthropic | `ANTHROPIC_API_KEY`  | ✅ shipped |

Install with the matching extra:

```bash
pip install 'videoink[openai]'           # or
pip install 'videoink[anthropic]'        # or both:
pip install 'videoink[openai,anthropic]'
```

Select at runtime:

```bash
videoink full <url> --provider openai     --model gpt-4o
videoink full <url> --provider anthropic  --model claude-sonnet-4-6
```

Per-provider defaults (when `--model` is omitted):

| Provider  | Default model      |
|-----------|--------------------|
| OpenAI    | `gpt-4o`           |
| Anthropic | `claude-sonnet-4-6`|

## Planned for v0.2

| Provider    | Env var              | Notes |
|-------------|----------------------|-------|
| OpenRouter  | `OPENROUTER_API_KEY` | one gateway → many models; chat only (no Whisper) |
| Ollama      | `OLLAMA_HOST`        | fully local; "your keys, your infra" story |

v0.2 will also land a **multi-model judge loop** — generate N article
drafts across providers, let another model pick the best. Tracked in
`ROADMAP.md`.

## Transcribe backend (separate from LLM provider)

The **transcribe** step has its own two engines, independent of the LLM
provider you pick above:

| `--engine` | Runs where | Needs key |
|------------|------------|-----------|
| `local`    | Your CPU via `faster-whisper` | No |
| `openai`   | OpenAI Whisper API (25 MB cap) | Yes (`OPENAI_API_KEY`) |

So it is possible to mix: transcribe locally, generate via Anthropic,
for example:

```bash
videoink full <url> --engine local --provider anthropic
```
