VENV := .venv
PYTHON := $(VENV)/bin/python
_PYTEST_GATE := $(filter 1 true yes,$(strip $(OOMPAH_PYTEST_GATE)))
ifeq ($(_PYTEST_GATE),)
PID_FILE ?= .oompah.pid
PID_META_FILE ?= .oompah.pid.meta
else
# A quality gate runs from a disposable worktree while the operator's service
# may be alive in another checkout.  Keep every lifecycle artifact under the
# gate's private run root so a test cannot discover the operator PID file.
PID_FILE := $(if $(OOMPAH_TEST_PID_FILE),$(OOMPAH_TEST_PID_FILE),$(OOMPAH_PYTEST_RUN_ROOT)/lifecycle/.oompah.pid)
PID_META_FILE := $(if $(OOMPAH_TEST_PID_META_FILE),$(OOMPAH_TEST_PID_META_FILE),$(OOMPAH_PYTEST_RUN_ROOT)/lifecycle/.oompah.pid.meta)
endif
LOG_FILE := oompah.log
# Read OOMPAH_SERVER_PORT from .env when not already in the shell environment.
# This makes `make status` and `make graceful` work consistently with the port
# oompah actually listens on, even when the operator hasn't exported the var.
_ENV_PORT := $(shell grep -E '^OOMPAH_SERVER_PORT[[:space:]]*=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' \t\r\n')
ifeq ($(_PYTEST_GATE),)
PORT ?= $(if $(OOMPAH_SERVER_PORT),$(OOMPAH_SERVER_PORT),$(if $(_ENV_PORT),$(_ENV_PORT),8080))
else
# The runner always supplies this ephemeral port.  Never fall back to .env or
# the operator's configured service port during a gate.
PORT := $(if $(OOMPAH_TEST_SERVER_PORT),$(OOMPAH_TEST_SERVER_PORT),0)
endif
LOCAL_HTTP_URL := http://127.0.0.1:$(PORT)
_ENV_DRAIN_TIMEOUT := $(shell grep -E '^OOMPAH_RESTART_DRAIN_TIMEOUT_SECONDS[[:space:]]*=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' \t\r\n')
DRAIN_TIMEOUT ?= $(if $(OOMPAH_RESTART_DRAIN_TIMEOUT_SECONDS),$(OOMPAH_RESTART_DRAIN_TIMEOUT_SECONDS),$(if $(_ENV_DRAIN_TIMEOUT),$(_ENV_DRAIN_TIMEOUT),3600))
RESTART_HEALTH_TIMEOUT ?= $(shell expr $(DRAIN_TIMEOUT) + 60)
_ENV_PYTEST_WORKERS := $(shell grep -E '^OOMPAH_PYTEST_WORKERS[[:space:]]*=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' \t\r\n')
PYTEST_WORKERS ?= $(if $(OOMPAH_PYTEST_WORKERS),$(OOMPAH_PYTEST_WORKERS),$(if $(_ENV_PYTEST_WORKERS),$(_ENV_PYTEST_WORKERS),4))
_ENV_TEMP_ROOT := $(shell grep -E '^OOMPAH_TEMP_ROOT[[:space:]]*=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' \t\r\n')
PYTEST_TEMP_ROOT ?= $(if $(OOMPAH_TEMP_ROOT),$(OOMPAH_TEMP_ROOT),$(if $(_ENV_TEMP_ROOT),$(_ENV_TEMP_ROOT),~/.oompah/tmp))
# Timeout (seconds) for waiting on process exit and port release during stop/restart.
STOP_TIMEOUT ?= 30
CANONICAL_CLI ?= $(if $(OOMPAH_CANONICAL_CLI),$(OOMPAH_CANONICAL_CLI),$(HOME)/.local/bin/oompah)
CLI_SOURCE_URL ?= $(if $(OOMPAH_CLI_SOURCE_URL),$(OOMPAH_CLI_SOURCE_URL),https://github.com/lesserevil/oompah)
UV ?= uv

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

.PHONY: help setup test-setup sync-cli install-cli start stop restart graceful force-restart status logs test test-serial terminal-audit-scan clean install-hooks check-secrets install-gh-extensions run-granian runner-setup runner-start runner-stop runner-status

help:
	@echo "oompah — make targets:"
	@echo "  setup          Install server dependencies into $(VENV) (idempotent)"
	@echo "  sync-cli       Install the exact clean pushed server revision at $(CANONICAL_CLI)"
	@echo "  install-cli    Alias for sync-cli"
	@echo "  start          Start oompah in the background (default port: $(PORT))"
	@echo "  stop           Stop the background oompah process"
	@echo "  restart        Drain active agents, restart in-place, and verify new process health"
	@echo "  graceful       Alias for the normal draining restart"
	@echo "  force-restart  Emergency hard stop + start; interrupts active agents"
	@echo "  status         Print PID + state JSON if running"
	@echo "  logs           Tail $(LOG_FILE)"
	@echo "  test           Run pytest in parallel (OOMPAH_PYTEST_WORKERS, default: 4)"
	@echo "  test-serial    Run pytest serially for race/debug diagnostics"
	@echo "  terminal-audit-scan  Reject unauthorized direct terminal tracker writes"
	@echo "  run-granian    Run oompah in the foreground using the Granian ASGI server (opt-in; see TASK-472)"
	@echo "  install-hooks  Install pre-commit hooks (idempotent) — runs gitleaks + secret scan on commit"
	@echo "  check-secrets  Run the paranoid secret scan over the whole tree (use before pushing)"
	@echo "  install-gh-extensions  Install gh CLI extensions oompah needs (cli/gh-webhook). Idempotent."
	@echo "  clean          Stop, then remove $(VENV), logs, pid file, and __pycache__ dirs"
	@echo "  runner-setup   Register the self-hosted Actions runner (requires GITHUB_TOKEN)"
	@echo "  runner-start   Start the containerized Actions runner"
	@echo "  runner-stop    Stop the containerized Actions runner"
	@echo "  runner-status  Show runner container status and GitHub registration state"

setup: $(VENV)/.uv-setup

$(VENV)/.uv-setup: pyproject.toml
	@test -d $(VENV) || uv venv $(VENV)
	uv pip install -e '.[server]'
	@touch $@
	@echo "Setup complete. Run 'make start' to launch oompah."

sync-cli: setup
	@$(PYTHON) scripts/sync_canonical_cli.py \
		--repo . \
		--canonical "$(CANONICAL_CLI)" \
		--source-url "$(CLI_SOURCE_URL)" \
		--uv "$(UV)"

install-cli: sync-cli

test-setup: $(VENV)/.uv-test-setup

$(VENV)/.uv-test-setup: pyproject.toml $(VENV)/.uv-setup
	uv pip install -e '.[dev]'
	@touch $@
	@echo "Test dependencies installed."

start: setup
	@mkdir -p "$$(dirname "$(PID_FILE)")" "$$(dirname "$(PID_META_FILE)")"; \
	EXISTING_PID=$$(cat "$(PID_FILE)" 2>/dev/null || true); \
	if [ -n "$$EXISTING_PID" ] && kill -0 "$$EXISTING_PID" 2>/dev/null; then \
		if [ ! -f "$(PID_META_FILE)" ] || \
			! $(PYTHON) scripts/process_identity.py verify "$$EXISTING_PID" "$$(pwd)" "$(PID_META_FILE)"; then \
			echo "ERROR: refusing to start over live PID $$EXISTING_PID without its exact stored identity." >&2; \
			echo "Run 'make restart' to migrate a verified pre-identity Oompah service, or inspect the PID and port manually." >&2; \
			exit 1; \
		fi; \
		echo "oompah is already running (pid $$EXISTING_PID)"; \
		$(PYTHON) scripts/canonical_cli_cutover.py \
			--repo . \
			--canonical "$(CANONICAL_CLI)" \
			--url "$(LOCAL_HTTP_URL)" \
			--verify-only || exit 1; \
	else \
		rm -f "$(PID_FILE)" "$(PID_META_FILE)"; \
		if $(call port_in_use,$(PORT)); then \
			echo "ERROR: Port $(PORT) is already in use. Cannot start oompah."; \
			exit 1; \
		fi; \
		$(PYTHON) scripts/sync_canonical_cli.py \
			--repo . \
			--canonical "$(CANONICAL_CLI)" \
			--source-url "$(CLI_SOURCE_URL)" \
			--uv "$(UV)" || exit 1; \
		if command -v setsid >/dev/null 2>&1; then \
			setsid $(PYTHON) -m oompah server >> $(LOG_FILE) 2>&1 </dev/null & \
		else \
			nohup $(PYTHON) -m oompah server >> $(LOG_FILE) 2>&1 </dev/null & \
		fi; \
		NEWPID=$$!; \
		echo $$NEWPID > "$(PID_FILE)"; \
		META_TMP=$$(mktemp "$(PID_META_FILE).tmp.XXXXXX"); \
		if ! $(PYTHON) scripts/process_identity.py capture "$$NEWPID" "$$(pwd)" > "$$META_TMP" 2>/dev/null || \
			! mv -f "$$META_TMP" "$(PID_META_FILE)"; then \
			echo "ERROR: oompah process $$NEWPID did not expose an owned process identity"; \
			kill -TERM $$NEWPID 2>/dev/null || true; \
			rm -f "$(PID_FILE)" "$(PID_META_FILE)" "$$META_TMP"; \
			exit 1; \
		fi; \
		echo "Waiting for oompah (pid $$NEWPID) to start listening on port $(PORT)..."; \
		ELAPSED=0; \
		while ! $(call port_in_use,$(PORT)); do \
			if [ $$ELAPSED -ge 10 ]; then \
				echo "ERROR: oompah (pid $$NEWPID) did not start listening on port $(PORT) within 10 seconds"; \
				rm -f "$(PID_FILE)" "$(PID_META_FILE)"; \
				exit 1; \
			fi; \
			if ! kill -0 $$NEWPID 2>/dev/null; then \
				echo "ERROR: oompah process $$NEWPID exited unexpectedly"; \
				rm -f "$(PID_FILE)" "$(PID_META_FILE)"; \
				exit 1; \
			fi; \
			sleep 1; \
			ELAPSED=$$((ELAPSED + 1)); \
		done; \
		if ! $(PYTHON) scripts/canonical_cli_cutover.py \
			--repo . \
			--canonical "$(CANONICAL_CLI)" \
			--url "$(LOCAL_HTTP_URL)" \
			--verify-only; then \
			echo "ERROR: oompah started but CLI/server build identities do not match; stopping it."; \
			$(MAKE) --no-print-directory stop; \
			exit 1; \
		fi; \
		echo "oompah started (pid $$NEWPID); HTTP port defaults to $(PORT)"; \
	fi

stop:
	@PID=$$(cat "$(PID_FILE)" 2>/dev/null || true); \
	if [ -n "$$PID" ] && kill -0 "$$PID" 2>/dev/null; then \
		if [ ! -f "$(PID_META_FILE)" ] || \
			! $(PYTHON) scripts/process_identity.py verify "$$PID" "$$(pwd)" "$(PID_META_FILE)"; then \
			echo "ERROR: refusing to stop live PID $$PID because its stored identity is missing or stale." >&2; \
			exit 1; \
		fi; \
		IDENTITY_META="$(PID_META_FILE)"; \
		if [ -r "$$IDENTITY_META" ]; then \
			GROUP=$$($(PYTHON) -c 'import json,sys; print(json.load(open(sys.argv[1]))["process_group"])' "$$IDENTITY_META"); \
			SESSION=$$($(PYTHON) -c 'import json,sys; print(json.load(open(sys.argv[1]))["session"])' "$$IDENTITY_META"); \
			if [ "$$GROUP" = "$$PID" ] && [ "$$SESSION" = "$$PID" ]; then kill -TERM -$$PID 2>/dev/null || kill $$PID; \
			else kill -TERM $$PID; fi; \
		else \
			echo "ERROR: refusing to stop PID $$PID without an owned identity" >&2; \
			exit 1; \
		fi; \
		$(call wait_for_stop,$$PID,$(PORT),$(STOP_TIMEOUT)); \
		rm -f "$(PID_FILE)" "$(PID_META_FILE)"; \
		echo "oompah stopped"; \
	else \
		rm -f "$(PID_FILE)" "$(PID_META_FILE)"; \
		echo "oompah is not running"; \
	fi

restart: setup
	@PID=$$(cat "$(PID_FILE)" 2>/dev/null || :); \
	if [ -n "$$PID" ] && kill -0 "$$PID" 2>/dev/null; then \
		HEALTHZ_URL="http://127.0.0.1:$(PORT)/healthz"; \
		if ! curl -sf "$$HEALTHZ_URL" >/dev/null; then \
			echo "ERROR: oompah PID is running but /healthz is unavailable."; \
			echo "Refusing to interrupt agents. Inspect logs, or use 'make force-restart' for an emergency."; \
			exit 1; \
		fi; \
		if [ -f "$(PID_META_FILE)" ]; then \
			if ! $(PYTHON) scripts/process_identity.py verify "$$PID" "$$(pwd)" "$(PID_META_FILE)"; then \
				echo "ERROR: refusing restart because PID $$PID no longer matches its stored identity." >&2; \
				exit 1; \
			fi; \
		else \
			echo "Migrating verified pre-identity service PID $$PID to an owned lifecycle record..."; \
			mkdir -p "$$(dirname "$(PID_META_FILE)")"; \
			META_TMP=$$(mktemp "$(PID_META_FILE).tmp.XXXXXX"); \
			if ! $(PYTHON) scripts/process_identity.py capture "$$PID" "$$(pwd)" > "$$META_TMP" 2>/dev/null; then \
				rm -f "$$META_TMP"; \
				echo "ERROR: refusing restart because PID $$PID is not owned by this checkout." >&2; \
				exit 1; \
			fi; \
			mv -f "$$META_TMP" "$(PID_META_FILE)"; \
		fi; \
		$(PYTHON) scripts/canonical_cli_cutover.py \
			--repo . \
			--canonical "$(CANONICAL_CLI)" \
			--url "$(LOCAL_HTTP_URL)" \
			--source-url "$(CLI_SOURCE_URL)" \
			--uv "$(UV)" \
			--timeout "$(DRAIN_TIMEOUT)" \
			--health-timeout "$(RESTART_HEALTH_TIMEOUT)" || exit 1; \
	else \
		rm -f "$(PID_FILE)" "$(PID_META_FILE)"; \
		echo "oompah is not running; starting it."; \
		make --no-print-directory start; \
	fi

graceful: restart

# The emergency path still stages before touching the running service.  It
# skips the graceful agent-drain wait, but activation and health verification
# remain transactional so an install failure cannot strand the old pair.
force-restart: setup
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		$(PYTHON) scripts/canonical_cli_cutover.py \
			--repo . \
			--canonical "$(CANONICAL_CLI)" \
			--url "$(LOCAL_HTTP_URL)" \
			--source-url "$(CLI_SOURCE_URL)" \
			--uv "$(UV)" \
			--force || exit 1; \
	else \
		$(MAKE) --no-print-directory start; \
	fi

# Run oompah in the foreground using the Granian ASGI server.
#
# Granian is an experimental opt-in server (~+23% HTTP throughput vs uvicorn,
# tighter tail latency). It must be run with a single worker because oompah
# holds shared in-process state; the orchestrator runs inside the worker's
# ASGI lifespan. See plans/codex-sdk-pin.md and TASK-472 for context.
#
# Requires: uv pip install -e '.[server,granian]'
run-granian:
	@if ! $(PYTHON) -c "import granian" 2>/dev/null; then \
		echo "granian is not installed. Run: uv pip install -e '.[server,granian]'"; \
		exit 1; \
	fi
	$(PYTHON) -m oompah server --server granian

status:
	@PID=$$(cat "$(PID_FILE)" 2>/dev/null || true); \
	if [ -n "$$PID" ] && kill -0 "$$PID" 2>/dev/null; then \
		if [ ! -f "$(PID_META_FILE)" ] || \
			! $(PYTHON) scripts/process_identity.py verify "$$PID" "$$(pwd)" "$(PID_META_FILE)"; then \
			echo "ERROR: live PID $$PID has no matching stored Oompah identity; refusing to discard its lifecycle files." >&2; \
			exit 1; \
		fi; \
		echo "oompah is running (pid $$PID)"; \
		echo "Dashboard: http://0.0.0.0:$(PORT)"; \
		if ! OOMPAH_SERVER_URL="$(LOCAL_HTTP_URL)" $(PYTHON) scripts/oompah_http.py GET /api/v1/state | python3 -m json.tool; then \
			echo "ERROR: Could not fetch state (check OOMPAH_SERVER_USERNAME / OOMPAH_SERVER_PASSWORD_FILE)."; \
			exit 1; \
		fi; \
	else \
		rm -f "$(PID_FILE)" "$(PID_META_FILE)"; \
		echo "oompah is not running"; \
	fi

test: test-setup terminal-audit-scan
	@OOMPAH_PYTEST_WORKERS="$(PYTEST_WORKERS)" \
		OOMPAH_PYTEST_TEMP_ROOT="$(PYTEST_TEMP_ROOT)" \
		scripts/run-tests.sh parallel

test-serial: test-setup
	@OOMPAH_PYTEST_TEMP_ROOT="$(PYTEST_TEMP_ROOT)" \
		scripts/run-tests.sh serial

terminal-audit-scan: test-setup
	@$(PYTHON) scripts/find_terminal_mutations.py oompah

logs:
	@tail -f $(LOG_FILE)

clean: stop
	rm -rf $(VENV) $(LOG_FILE) $(PID_FILE) $(PID_META_FILE) oompah.egg-info
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

# ---------------------------------------------------------------------------
# Self-hosted GitHub Actions runner (containerized via Podman/Docker)
# See docs/self-hosted-runner.md for setup and troubleshooting.
# ---------------------------------------------------------------------------

runner-setup:
	@bash scripts/runner.sh setup

runner-start:
	@bash scripts/runner.sh start

runner-stop:
	@bash scripts/runner.sh stop

runner-status:
	@bash scripts/runner.sh status
