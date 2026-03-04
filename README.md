# PromptLayer Claude Code Plugin

See every Claude Code session as structured traces in [PromptLayer](https://promptlayer.com) — user messages, assistant responses, tool calls, and token usage, all captured automatically.

## Quick Start

### 1. Install

```bash
claude plugin marketplace add MagnivOrg/promptlayer-claude-plugins
claude plugin install trace@promptlayer-claude-plugins
```

### 2. Configure

Run the setup script from the project where you want tracing enabled:

```bash
$HOME/.claude/plugins/marketplaces/promptlayer-claude-plugins/plugins/trace/setup.sh
```

You will be prompted for your PromptLayer API key. You can find or create one at [dashboard.promptlayer.com](https://dashboard.promptlayer.com).

### 3. Verify

1. Start Claude Code: `claude`
2. Send a prompt
3. Check your traces at [dashboard.promptlayer.com](https://dashboard.promptlayer.com)

## What Gets Traced

The plugin hooks into Claude Code's lifecycle and emits [OTLP/HTTP JSON](docs/otlp-mapping.md) spans for:

- **Sessions** — one root span per Claude Code session
- **LLM calls** — model, token counts, prompts, and completions
- **Tool calls** — tool name, input, and output

## Prerequisites

- Claude Code CLI installed
- A PromptLayer account and API key ([dashboard.promptlayer.com](https://dashboard.promptlayer.com))
- `jq`, `curl`, `uuidgen`, and `python3` available in your shell
- **macOS** or **Linux** (tested on Ubuntu)

## Configuration

The setup script writes `~/.claude/settings.json` with:

| Variable | Purpose | Default |
|----------|---------|---------|
| `TRACE_TO_PROMPTLAYER` | Enable/disable tracing | `true` |
| `PROMPTLAYER_API_KEY` | Your API key | _(required)_ |
| `PROMPTLAYER_OTLP_ENDPOINT` | OTLP ingestion endpoint | `https://api.promptlayer.com/v1/traces` |
| `PROMPTLAYER_CC_DEBUG` | Enable debug logging | `false` |

Because this file lives in your home directory, your API key stays out of version control and tracing is enabled across all projects.

## OTLP-Native Tracing

This plugin is **OpenTelemetry (OTLP/HTTP JSON)** compatible:

- **Open standard** — traces follow the [OTLP specification](https://opentelemetry.io/docs/specs/otlp/), not a vendor-specific format
- **Portable** — swap or fan-out to any OTLP-compatible backend (Datadog, Honeycomb, Grafana Tempo, etc.) by changing one endpoint URL
- **No SDK lock-in** — the plugin uses plain `curl` to send `ExportTraceServiceRequest` payloads; no proprietary client libraries required

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md).

## Local Development

```bash
make dev        # Symlink repo as marketplace source, install plugin, run setup
make uninstall  # Remove local install and cleanup artifacts
make test       # Validate manifests + lint + fixture replay
make smoke      # E2E smoke test (requires ANTHROPIC_API_KEY)
```
