VENV := .venv
PYTHON := $(VENV)/bin/python
PID_FILE := .oompah.pid
LOG_FILE := oompah.log
# Read OOMPAH_SERVER_PORT from .env when not already in the shell environment.
# This makes `make status` and `make graceful` work consistently with the port
# oompah actually listens on, even when the operator hasn't exported the var.
_ENV_PORT := $(shell grep -E '^OOMPAH_SERVER_PORT[[:space:]]*=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' \t\r\n')
PORT ?= $(if $(OOMPAH_SERVER_PORT),$(OOMPAH_SERVER_PORT),$(if $(_ENV_PORT),$(_ENV_PORT),8080))
# Timeout (seconds) for waiting on process exit and port release during stop/restart.
STOP_TIMEOUT ?= 30
BACKLOG_NPM_PACKAGE := https://github.com/MrLesk/Backlog.md/archive/HEAD.tar.gz
BACKLOG_CLI := $(VENV)/bin/backlog

export PATH := $(abspath $(VENV)/bin):$(PATH)

# Internal helper: wait for a PID to exit, then wait for the port to be free.
# Usage: $(call wait_for_stop,PID,PORT,TIMEOUT)
# Returns 0 on success, non-zero on timeout.
# NOTE: do NOT start this define body with @ — when expanded inline inside
# another recipe (e.g. the stop target) the @ becomes a literal shell character
# and causes a "command not found" error.  Echo suppression is handled by the
# outer recipe's leading @.
define wait_for_stop
	PID=$1; PORT=$2; TIMEOUT=$3; \
	echo "Waiting for process $$PID to exit and port $$PORT to be released (timeout: $${TIMEOUT}s)..."; \
	ELAPSED=0; \
	while kill -0 $$PID 2>/dev/null; do \
		if [ $$ELAPSED -ge $${TIMEOUT} ]; then \
			echo "ERROR: Process $$PID did not exit within $${TIMEOUT} seconds"; \
			exit 1; \
		fi; \
		sleep 1; \
		ELAPSED=$$((ELAPSED + 1)); \
	done; \
	echo "Process $$PID exited. Waiting for port $$PORT to be released..."; \
	ELAPSED=0; \
	while $(call port_in_use,$$PORT); do \
		if [ $$ELAPSED -ge $${TIMEOUT} ]; then \
			echo "ERROR: Port $$PORT not released within $${TIMEOUT} seconds after process exit"; \
			exit 1; \
		fi; \
		sleep 1; \
		ELAPSED=$$((ELAPSED + 1)); \
	done; \
	echo "Port $$PORT is free."
endef

# Internal helper: check if a port is in use (LISTEN state).
# Usage: $(call port_in_use,PORT)
# Returns 0 (true) if port is in use, 1 (false) if free.
# Uses ss if available, falls back to lsof.
define port_in_use
	command -v ss >/dev/null 2>&1 && ss -ltn "sport = :$1" 2>/dev/null | grep -q LISTEN; \
	[ $$? -eq 0 ] || (command -v lsof >/dev/null 2>&1 && lsof -ti:"$1" -sTCP:LISTEN 2>/dev/null | grep -q .)
endef

.PHONY: help setup ensure-backlog start stop restart graceful status logs test clean install-hooks check-secrets install-gh-extensions run-granian

help:
	@echo "oompah — make targets:"
	@echo "  setup          Install server dependencies and Backlog.md CLI into $(VENV) (idempotent)"
	@echo "  start          Start oompah in the background (default port: $(PORT))"
	@echo "  stop           Stop the background oompah process"
	@echo "  restart        Hard restart (stop + start) — use for orchestrator/agent changes"
	@echo "  graceful       Drain running agents and restart in-place — use for cosmetic/template changes"
	@echo "  status         Print PID + state JSON if running"
	@echo "  logs           Tail $(LOG_FILE)"
	@echo "  test           Run the pytest suite"
	@echo "  run-granian    Run oompah in the foreground using the Granian ASGI server (opt-in; see TASK-472)"
	@echo "  install-hooks  Install pre-commit hooks (idempotent) — runs gitleaks + secret scan on commit"
	@echo "  check-secrets  Run the paranoid secret scan over the whole tree (use before pushing)"
	@echo "  install-gh-extensions  Install gh CLI extensions oompah needs (cli/gh-webhook). Idempotent."
	@echo "  clean          Stop, then remove $(VENV), logs, pid file, and __pycache__ dirs"

setup: $(VENV)/.uv-setup ensure-backlog

$(VENV)/.uv-setup: pyproject.toml
	@test -d $(VENV) || uv venv $(VENV)
	uv pip install -e '.[server]'
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
		if $(call port_in_use,$(PORT)); then \
			echo "ERROR: Port $(PORT) is already in use. Cannot start oompah."; \
			exit 1; \
		fi; \
		if command -v setsid >/dev/null 2>&1; then \
			setsid $(PYTHON) -m oompah >> $(LOG_FILE) 2>&1 </dev/null & \
		else \
			nohup $(PYTHON) -m oompah >> $(LOG_FILE) 2>&1 </dev/null & \
		fi; \
		NEWPID=$$!; \
		echo $$NEWPID > $(PID_FILE); \
		echo "Waiting for oompah (pid $$NEWPID) to start listening on port $(PORT)..."; \
		ELAPSED=0; \
		while ! $(call port_in_use,$(PORT)); do \
			if [ $$ELAPSED -ge 10 ]; then \
				echo "ERROR: oompah (pid $$NEWPID) did not start listening on port $(PORT) within 10 seconds"; \
				rm -f $(PID_FILE); \
				exit 1; \
			fi; \
			if ! kill -0 $$NEWPID 2>/dev/null; then \
				echo "ERROR: oompah process $$NEWPID exited unexpectedly"; \
				rm -f $(PID_FILE); \
				exit 1; \
			fi; \
			sleep 1; \
			ELAPSED=$$((ELAPSED + 1)); \
		done; \
		echo "oompah started (pid $$NEWPID); HTTP port defaults to $(PORT)"; \
	fi

stop:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		PID=$$(cat $(PID_FILE)); \
		kill -TERM -$$PID 2>/dev/null || kill $$PID; \
		$(call wait_for_stop,$$PID,$(PORT),$(STOP_TIMEOUT)); \
		rm -f $(PID_FILE); \
		echo "oompah stopped"; \
	else \
		rm -f $(PID_FILE); \
		echo "oompah is not running"; \
	fi

restart: stop start

# Run oompah in the foreground using the Granian ASGI server.
#
# Granian is an experimental opt-in server (~+23% HTTP throughput vs uvicorn,
# tighter tail latency). It must be run with a single worker because oompah
# holds shared in-process state; the orchestrator runs inside the worker's
# ASGI lifespan. See backlog/docs/doc-1 (Granian HTTP server migration plan)
# and TASK-472 for context.
#
# Requires: uv pip install -e '.[server,granian]'
run-granian:
	@if ! $(PYTHON) -c "import granian" 2>/dev/null; then \
		echo "granian is not installed. Run: uv pip install -e '.[server,granian]'"; \
		exit 1; \
	fi
	$(PYTHON) -m oompah --server granian

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
