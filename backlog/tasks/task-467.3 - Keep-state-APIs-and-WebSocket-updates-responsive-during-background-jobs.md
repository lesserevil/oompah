---
id: TASK-467.3
title: Keep state APIs and WebSocket updates responsive during background jobs
status: In Progress
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-09 05:02'
labels:
  - task
  - tick-latency
  - responsiveness
dependencies:
  - TASK-466.4
  - TASK-467.2
references:
  - oompah/server.py
  - oompah/orchestrator.py
modified_files:
  - oompah/server.py
  - oompah/orchestrator.py
  - tests/test_server_issue_detail.py
  - tests/test_dashboard_running_agent_project_filter.py
parent_task_id: TASK-467
ordinal: 13
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ensure /api/v1/state, dashboard WebSocket state broadcasts, and status rendering use cached snapshots or lock-free reads instead of waiting behind long maintenance jobs. Avoid exposing tokens or secret project fields when surfacing maintenance and timing diagnostics.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 State API calls return promptly while maintenance is running.
- [ ] #2 WebSocket state broadcasts continue to reflect running agents and maintenance status.
- [ ] #3 Diagnostics included in API responses are secret-safe.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 20:13
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 20:13
---
Focus: Frontend Developer
---

author: oompah
created: 2026-06-08 20:19
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 68
- Tokens: 93 in / 3.8K out [3.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 6m 28s
- Log: TASK-467.3__20260608T201449Z.jsonl
---

author: oompah
created: 2026-06-09 04:40
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 04:50
---
Understanding: TASK-467.3 is NOT a duplicate. TASK-469.5 implemented multi-process IPC caching and improved the issues endpoint, but left gaps that TASK-467.3 addresses: (1) In combined/single-process mode, /api/v1/state still calls orch.get_snapshot() live on every request with no caching. (2) get_snapshot() exposes raw project access_token and webhook_secret through p.to_dict() — a confirmed security issue. (3) WebSocket state broadcasts are already responsive (receive snapshot from observer callbacks), but the snapshot itself contains unredacted secrets. Plan: (a) Fix get_snapshot() to use safe project serialization that redacts secrets, (b) add a server-side state snapshot cache updated by observer callbacks so api_state() in combined mode never waits on maintenance, (c) write tests for both.
---

author: oompah
created: 2026-06-09 05:02
---
Discovery: Found two concrete issues: (1) SECURITY: get_snapshot() in orchestrator.py used p.to_dict() for the projects field, which included raw access_token and webhook_secret in all /api/v1/state responses and WebSocket broadcasts. (2) REGRESSION BUG: TASK-467.2 merge placed self._ipc and self._arm_profile_drift_alert() as dead code inside _run_bounded_refresh() instead of __init__(), causing AttributeError: 'Orchestrator' object has no attribute '_ipc' in all Orchestrator instantiation paths (test_submit_queue_concurrency, test_project_pause, test_ipc all failed). (3) RESPONSIVENESS: api_state() in combined mode called get_snapshot() live on every request with no caching, even during GIL-heavy maintenance.
---

author: oompah
created: 2026-06-09 05:02
---
Implementation: (1) models.py: Updated to_safe_dict() to also remove webhook_secret (was only removing access_token), adds has_webhook_secret flag. (2) orchestrator.py: Changed get_snapshot() to use p.to_safe_dict() instead of p.to_dict() for projects field — removes raw secrets from all state API responses and WebSocket broadcasts. Also fixed the regression bug where _ipc initialization and _arm_profile_drift_alert() call were placed as dead code inside _run_bounded_refresh() instead of __init__() due to a bad TASK-467.2 merge — moved them to the correct location in __init__(). (3) server.py: Added _state_snapshot_cache infrastructure (_update_state_snapshot, _read_state_snapshot, _STATE_SNAPSHOT_MAX_AGE_S=30s). Updated observer callbacks (_on_orchestrator_change, _on_state_only_change) to always cache the received snapshot. Updated api_state() to prefer cached snapshot in combined mode, falling back to live get_snapshot() only when cache is empty or expired. (4) tests/test_state_api_responsiveness.py: 19 new tests covering all 3 ACs.
---
<!-- COMMENTS:END -->
