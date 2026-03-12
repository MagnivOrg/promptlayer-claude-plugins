SHELL := /bin/bash

.PHONY: dev uninstall validate lint test smoke

dev:
	./scripts/dev-install.sh

uninstall:
	./scripts/dev-uninstall.sh

validate:
	./scripts/validate-manifests.sh

lint:
	if command -v shellcheck >/dev/null 2>&1; then shellcheck -x plugins/trace/hooks/*.sh plugins/trace/setup.sh scripts/*.sh; else echo "shellcheck not installed, skipping"; fi
	if command -v shfmt >/dev/null 2>&1; then shfmt -d plugins/trace/hooks/*.sh plugins/trace/setup.sh scripts/*.sh; else echo "shfmt not installed, skipping"; fi

test: validate lint
	./scripts/replay-fixtures.sh

smoke:
	./scripts/e2e_smoke.py
