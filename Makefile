VENV := .venv
PYTHON := $(VENV)/bin/python
PID_FILE := .oompah.pid
LOG_FILE := oompah.log
PORT := 8080

.PHONY: setup start stop restart graceful status logs clean

setup: $(VENV)/.uv-setup

$(VENV)/.uv-setup: pyproject.toml
	@test -d $(VENV) || uv venv $(VENV)
	uv pip install -e .
	@touch $@
	@echo "Setup complete. Run 'make start' to launch oompah."

start: setup
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "oompah is already running (pid $$(cat $(PID_FILE)))"; \
	else \
		$(PYTHON) -m oompah --port $(PORT) >> $(LOG_FILE) 2>&1 & \
		echo $$! > $(PID_FILE); \
		echo "oompah started (pid $$!) on http://0.0.0.0:$(PORT)"; \
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

logs:
	@tail -f $(LOG_FILE)

clean: stop
	rm -rf $(VENV) $(LOG_FILE) $(PID_FILE) oompah.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned up"
