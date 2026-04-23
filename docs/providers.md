# LLM providers

`videoink` supports multiple LLM backends for the `generate` / `full`
subcommands (the **standalone CLI path**). Inside Claude Code, the
skill-native workflow skips `videoink generate` entirely and lets
Claude Code itself write the article — no provider / key needed there.

## Shipping in v0.3

| Provider    | Env var / host         | Status |
|-------------|------------------------|--------|
| OpenAI      | `OPENAI_API_KEY`       | ✅ shipped (v0.1) |
| Anthropic   | `ANTHROPIC_API_KEY`    | ✅ shipped (v0.1) |
| OpenRouter  | `OPENROUTER_API_KEY`   | ✅ shipped (v0.3) — one gateway → many models |
| Ollama      | `OLLAMA_HOST` (optional, default `localhost:11434`) | ✅ shipped (v0.3) — fully local, no API key |

Install with the matching extra. OpenRouter and Ollama both use the `openai` SDK:

```bash
pip install 'videoink[openai]'                    # OpenAI + OpenRouter + Ollama
pip install 'videoink[anthropic]'                 # Anthropic only
pip install 'videoink[openai,anthropic]'          # both
```

Select at runtime:

```bash
videoink full <url> --provider openai      --model gpt-4o
videoink full <url> --provider anthropic   --model claude-sonnet-4-6
videoink full <url> --provider openrouter  --model anthropic/claude-sonnet-4.5
videoink full <url> --provider ollama      --model llama3.2
```

Per-provider defaults (when `--model` is omitted):

| Provider    | Default model              |
|-------------|----------------------------|
| OpenAI      | `gpt-4o`                   |
| Anthropic   | `claude-sonnet-4-6`        |
| OpenRouter  | `openai/gpt-4o-mini`       |
| Ollama      | `llama3.2`                 |

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

### Ollama setup (local inference)

Install Ollama ([ollama.com/download](https://ollama.com/download)),
pull a model, and run the server:

```bash
ollama pull llama3.2           # or qwen2.5, deepseek-r1, mistral, ...
ollama serve                   # listens on localhost:11434 by default
```

Then point `videoink` at it:

```bash
videoink full <url> --engine local --provider ollama --model llama3.2
```

For a remote Ollama (e.g. GPU box on your LAN):

```bash
export OLLAMA_HOST=gpu-box:11434           # bare host:port → http://
# or a full URL:
export OLLAMA_HOST=https://ollama.example.com:8443
```

Ollama doesn't require an API key; the OpenAI SDK does require a
non-empty string, so `videoink` sends the sentinel `"ollama"` which the
server ignores.

## Planned for v0.4+

- **Multi-model judge loop**: generate N article drafts across
  providers, let another model pick the best. Tracked in `ROADMAP.md`.

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
