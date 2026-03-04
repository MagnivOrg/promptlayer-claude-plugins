# PromptLayer Claude Code Plugin Marketplace

Open source Claude Code plugin marketplace for PromptLayer tracing.

## Plugin

- `pl-trace-claude-code`: traces Claude Code sessions and emits OTLP/HTTP JSON spans to PromptLayer.

## Prerequisites

- Claude Code CLI installed
- PromptLayer API key (`PROMPTLAYER_API_KEY`)
- `jq`, `curl`, `uuidgen`, and `python3` available in your shell

## Install

```bash
claude plugin marketplace add promptlayer/promptlayer-claude-plugin
claude plugin install pl-trace-claude-code@promptlayer-claude-plugin
```

## Configure

Run the setup script from the project where you want tracing enabled:

```bash
$HOME/.claude/plugins/marketplaces/promptlayer-claude-plugin/plugins/pl-trace-claude-code/setup.sh
```

The script writes `.claude/settings.local.json` with:

- `TRACE_TO_PROMPTLAYER=true`
- `PROMPTLAYER_API_KEY`
- `PROMPTLAYER_OTLP_ENDPOINT` (default: `https://api.promptlayer.com/v1/traces`)
- `PROMPTLAYER_CC_DEBUG`

## Verify

1. Start Claude Code in the configured directory: `claude`
2. Send a prompt and use at least one tool
3. Check hook logs: `tail -f ~/.claude/state/promptlayer_hook.log`

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md).

## Local Development

Install from this local repo and run setup:

```bash
make dev
```

`make dev` symlinks this repo as the marketplace source, installs `pl-trace-claude-code`, and runs the setup script.

Remove the local plugin install and cleanup local artifacts:

```bash
make uninstall
```

Run validation + lint + fixture replay:

```bash
make test
```

Run end-to-end SDK smoke test (requires `ANTHROPIC_API_KEY`):

```bash
make smoke
```
