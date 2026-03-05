VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PID_FILE := .umpah.pid
LOG_FILE := umpah.log
PORT := 8080

.PHONY: setup start stop restart status logs clean

setup: $(VENV)/bin/activate

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install -e .
	@echo "Setup complete. Run 'make start' to launch umpah."

start: setup
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "umpah is already running (pid $$(cat $(PID_FILE)))"; \
	else \
		$(PYTHON) -m umpah --port $(PORT) >> $(LOG_FILE) 2>&1 & \
		echo $$! > $(PID_FILE); \
		echo "umpah started (pid $$!) on http://127.0.0.1:$(PORT)"; \
	fi

stop:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		kill $$(cat $(PID_FILE)); \
		rm -f $(PID_FILE); \
		echo "umpah stopped"; \
	else \
		rm -f $(PID_FILE); \
		echo "umpah is not running"; \
	fi

restart: stop start

status:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "umpah is running (pid $$(cat $(PID_FILE)))"; \
		echo "Dashboard: http://127.0.0.1:$(PORT)"; \
		curl -s http://127.0.0.1:$(PORT)/api/v1/state 2>/dev/null | python3 -m json.tool || true; \
	else \
		rm -f $(PID_FILE); \
		echo "umpah is not running"; \
	fi

logs:
	@tail -f $(LOG_FILE)

clean: stop
	rm -rf $(VENV) $(LOG_FILE) $(PID_FILE) umpah.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned up"
