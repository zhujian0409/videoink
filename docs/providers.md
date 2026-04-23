# LLM providers

`videoink` supports multiple LLM backends for the `generate` / `full`
subcommands (the **standalone CLI path**). Inside Claude Code, the
skill-native workflow skips `videoink generate` entirely and lets
Claude Code itself write the article — no provider / key needed there.

## Shipping in v0.3

| Provider    | Env var                | Status |
|-------------|------------------------|--------|
| OpenAI      | `OPENAI_API_KEY`       | ✅ shipped (v0.1) |
| Anthropic   | `ANTHROPIC_API_KEY`    | ✅ shipped (v0.1) |
| OpenRouter  | `OPENROUTER_API_KEY`   | ✅ shipped (v0.3) — one gateway → many models |

Install with the matching extra. OpenRouter uses the `openai` SDK:

```bash
pip install 'videoink[openai]'                    # OpenAI + OpenRouter
pip install 'videoink[anthropic]'                 # Anthropic only
pip install 'videoink[openai,anthropic]'          # both
```

Select at runtime:

```bash
videoink full <url> --provider openai      --model gpt-4o
videoink full <url> --provider anthropic   --model claude-sonnet-4-6
videoink full <url> --provider openrouter  --model anthropic/claude-sonnet-4.5
```

Per-provider defaults (when `--model` is omitted):

| Provider    | Default model              |
|-------------|----------------------------|
| OpenAI      | `gpt-4o`                   |
| Anthropic   | `claude-sonnet-4-6`        |
| OpenRouter  | `openai/gpt-4o-mini`       |

### OpenRouter attribution headers (optional)

OpenRouter lets apps opt into its site-attribution leaderboards. If you
want your traffic counted, set:

```bash
export OPENROUTER_HTTP_REFERER=https://your.site
export OPENROUTER_X_TITLE=videoink
```

These are forwarded as `HTTP-Referer` / `X-Title` headers and are
completely optional — omit them and OpenRouter treats the calls as
anonymous.

## Planned for v0.4

| Provider    | Env var              | Notes |
|-------------|----------------------|-------|
| Ollama      | `OLLAMA_HOST`        | fully local; "your keys, your infra" story |

Also on the backlog: a **multi-model judge loop** — generate N article
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
