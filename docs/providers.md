# LLM providers

`videoink` supports multiple LLM backends. Set the env var for the
provider you want; the CLI auto-detects which is configured.

| Provider   | Env var              | Status |
|------------|----------------------|--------|
| OpenAI     | `OPENAI_API_KEY`     | Planned for v0.1 |
| Anthropic  | `ANTHROPIC_API_KEY`  | Planned for v0.1 |
| OpenRouter | `OPENROUTER_API_KEY` | v0.2 |
| Ollama     | `OLLAMA_HOST`        | v0.2 |

Details and model selection guidance coming with v0.1.
