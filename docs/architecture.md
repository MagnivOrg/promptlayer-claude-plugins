# Architecture

The plugin emits OTLP/HTTP JSON traces from Claude Code hook events.

Core components:

- `setup.sh`: onboarding and local env configuration.
- `hooks/hooks.json`: hook registration.
- `hooks/lib.sh`: shared state, OTLP payload construction, transport.
- `hooks/*.sh`: event-specific span creation.
