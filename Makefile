VENV := .venv
PYTHON := $(VENV)/bin/python
PID_FILE := .oompah.pid
LOG_FILE := oompah.log
# Read OOMPAH_SERVER_PORT from .env when not already in the shell environment.
# This makes `make status` and `make graceful` work consistently with the port
# oompah actually listens on, even when the operator hasn't exported the var.
_ENV_PORT := $(shell grep -E '^OOMPAH_SERVER_PORT[[:space:]]*=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' \t\r\n')
PORT ?= $(if $(OOMPAH_SERVER_PORT),$(OOMPAH_SERVER_PORT),$(if $(_ENV_PORT),$(_ENV_PORT),8080))
BACKLOG_NPM_PACKAGE := https://github.com/lesserevil/backlog.md/archive/HEAD.tar.gz
BACKLOG_CLI := $(VENV)/bin/backlog

export PATH := $(abspath $(VENV)/bin):$(PATH)

.PHONY: help setup ensure-backlog start stop restart graceful status logs test clean install-hooks check-secrets install-gh-extensions

help:
	@echo "oompah — make targets:"
	@echo "  setup          Install dependencies and Backlog.md CLI into $(VENV) (idempotent)"
	@echo "  start          Start oompah in the background (default port: $(PORT))"
	@echo "  stop           Stop the background oompah process"
	@echo "  restart        Hard restart (stop + start) — use for orchestrator/agent changes"
	@echo "  graceful       Drain running agents and restart in-place — use for cosmetic/template changes"
	@echo "  status         Print PID + state JSON if running"
	@echo "  logs           Tail $(LOG_FILE)"
	@echo "  test           Run the pytest suite"
	@echo "  install-hooks  Install pre-commit hooks (idempotent) — runs gitleaks + secret scan on commit"
	@echo "  check-secrets  Run the paranoid secret scan over the whole tree (use before pushing)"
	@echo "  install-gh-extensions  Install gh CLI extensions oompah needs (cli/gh-webhook). Idempotent."
	@echo "  clean          Stop, then remove $(VENV), logs, pid file, and __pycache__ dirs"

setup: $(VENV)/.uv-setup ensure-backlog

$(VENV)/.uv-setup: pyproject.toml
	@test -d $(VENV) || uv venv $(VENV)
	uv pip install -e .
	@touch $@
	@echo "Setup complete. Run 'make start' to launch oompah."

ensure-backlog: $(BACKLOG_CLI)
	@echo "Backlog.md CLI available: $$(backlog --version 2>/dev/null || echo unknown)"

$(BACKLOG_CLI): $(VENV)/.uv-setup Makefile
	@if ! command -v npm >/dev/null 2>&1; then \
		echo "ERROR: npm is required to install Backlog.md from $(BACKLOG_NPM_PACKAGE)."; \
		exit 1; \
	fi
	@echo "Installing Backlog.md CLI from $(BACKLOG_NPM_PACKAGE) into $(abspath $(VENV))..."
	npm install --global --prefix "$(abspath $(VENV))" --ignore-scripts --no-audit --no-fund "$(BACKLOG_NPM_PACKAGE)"
	@test -x "$(VENV)/bin/backlog"

start: setup
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "oompah is already running (pid $$(cat $(PID_FILE)))"; \
	else \
		if command -v setsid >/dev/null 2>&1; then \
			setsid $(PYTHON) -m oompah >> $(LOG_FILE) 2>&1 </dev/null & \
		else \
			nohup $(PYTHON) -m oompah >> $(LOG_FILE) 2>&1 </dev/null & \
		fi; \
		echo $$! > $(PID_FILE); \
		echo "oompah started (pid $$!); HTTP port defaults to $(PORT)"; \
	fi

stop:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		kill $$(cat $(PID_FILE)); \
		rm -f $(PID_FILE); \
		echo "oompah stopped"; \
	else \
		rm -f $(PID_FILE); \
		echo "oompah is not running"; \
	fi

restart: stop start

graceful:
	@curl -sf -X POST http://0.0.0.0:$(PORT)/api/v1/orchestrator/restart \
		-H 'Content-Type: application/json' -d '{"drain_timeout_s": 60}' \
		| python3 -m json.tool \
		&& echo "Graceful restart initiated" \
		|| echo "Failed — is oompah running?"

status:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "oompah is running (pid $$(cat $(PID_FILE)))"; \
		echo "Dashboard: http://0.0.0.0:$(PORT)"; \
		curl -s http://0.0.0.0:$(PORT)/api/v1/state 2>/dev/null | python3 -m json.tool || true; \
	else \
		rm -f $(PID_FILE); \
		echo "oompah is not running"; \
	fi

test: setup
	uv run pytest tests/ -v

logs:
	@tail -f $(LOG_FILE)

clean: stop
	rm -rf $(VENV) $(LOG_FILE) $(PID_FILE) oompah.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned up"

install-hooks: setup
	@echo "Installing pre-commit hooks..."
	@uv pip install pre-commit
	@$(VENV)/bin/pre-commit install
	@echo "Pre-commit hooks installed. They run automatically on git commit."
	@echo "To run manually: $(VENV)/bin/pre-commit run --all-files"

check-secrets:
	@scripts/check-secrets.sh --all

# Install the gh CLI extensions oompah depends on. Currently just the
# cli/gh-webhook extension used by WebhookForwarder to forward forge
# webhook events to the local oompah server. Idempotent: skips
# installation if the extension is already present.
install-gh-extensions:
	@if ! command -v gh >/dev/null 2>&1; then \
		echo "ERROR: 'gh' CLI not found. Install from https://cli.github.com/ first."; \
		exit 1; \
	fi
	@if gh webhook --help >/dev/null 2>&1; then \
		echo "gh-webhook extension already installed."; \
	else \
		echo "Installing cli/gh-webhook extension..."; \
		gh extension install cli/gh-webhook; \
		echo "Done. Verify with: gh webhook --help"; \
	fi
