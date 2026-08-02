---
id: OOMPAH-690
type: task
status: In Progress
priority: null
title: Restore reliable automatic dashboard updates
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T00:37:18.141681Z'
updated_at: '2026-08-02T00:41:02.136609Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4448eb9e9bf16ed805655767845203a2dd0fe95eded17aba4e22100a9a603172
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T00:40:43.849630+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation of all task directories (open,\
    \ merged, archived, backlog) and project documentation, I have completed the duplicate\
    \ screening for OOMPAH-690.\n\n**Search scope covered:**\n- `.oompah/tasks/open/`\
    \ \u2014 1 task (OOMPAH-281: GitHub Actions runner setup \u2014 unrelated)\n-\
    \ `.oompah/tasks/backlog/` \u2014 1 task (OOMPAH-282: state_branch_migration error\
    \ \u2014 unrelated)\n- `.oompah/tasks/merged/` \u2014 7 tasks (all maintenance/infrastructure:\
    \ epic rebase, YOLO watchdog, runner setup \u2014 unrelated)\n- `.oompah/tasks/archived/`\
    \ \u2014 276 tasks (comprehensive keyword search)\n- `docs/`, `plans/`, `README.md`,\
    \ `WORKFLOW.md`\n\n**Keywords searched:**\n- WebSocket: `websocket`, `socket`,\
    \ `ws:`, `wss:`, `connectWebSocket`\n- Dashboard/Updates: `dashboard`, `broadcast`,\
    \ `live.*update`, `live.*dash`, `board.*change`\n- Refresh/Reconnect: `refresh`,\
    \ `reconnect`, `heartbeat`, `liveness`, `state.*only`\n- Server/Observer: `_on_orchestrator_change`,\
    \ `_throttled_broadcast`, `_last_state_broadcast`, `observer`, `emit.*event`,\
    \ `notify.*browser`\n- Throttle/State: `throttle`, `500.*ms`, `issue.*notification`,\
    \ `orchestrator.*notification`, `agent.*activity`\n\n**Result:** \nAll searches\
    \ returned **no matches** for any existing task covering dashboard WebSocket connectivity,\
    \ automatic update delivery, heartbeat mechanisms, or related browser-side reconnect/liveness\
    \ handling. The only active (non-terminal) task is OOMPAH-281, which is entirely\
    \ unrelated (GitHub Actions runner containerization).\n\n---\n\n**Focus handoff:\
    \ duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\n**Matches:\
    \ none**\n\n**Evidence:** Comprehensive search of all task tracker states (open,\
    \ merged, archived, backlog), project documentation (docs/, plans/), and repository\
    \ configuration files found zero existing tasks addressing dashboard WebSocket\
    \ connectivity, automatic issue-change propagation, browser heartbeat/liveness\
    \ detection, or throttle-window message coalescing. OOMPAH-690 is a genuine, first-of-its-kind"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4ec82bd5-1f8b-4a3c-a842-74976f408879
oompah.task_costs:
  total_input_tokens: 146
  total_output_tokens: 4598
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 146
      output_tokens: 4598
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 146
    output_tokens: 4598
    cost_usd: 0.0
    recorded_at: '2026-08-02T00:40:43.848773+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-690__20260802T003910Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-690
    source_sha: 7e0d0d8c766219d9ced2f2b502f6c5cf4becf4cd
    completed_at: '2026-08-02T00:40:43.882534+00:00'
---
## Summary

The live dashboard remains WebSocket-connected but task and alert changes can require a browser refresh before appearing. A concrete server loss path exists in oompah.server._on_orchestrator_change: state-only agent activity and issue-changing notifications share _last_state_broadcast. If activity updates the timestamp less than 500 ms before a task transition, _on_orchestrator_change returns before scheduling _throttled_broadcast_issues, permanently dropping that board refresh. The browser also sends no heartbeat, so a silently severed proxy connection can remain apparently Connected without forcing reconnect/backfill.

Implementation scope:
- Ensure every issue-changing orchestrator notification schedules a throttled/debounced issues refresh even when its state message is suppressed by the state throttle.
- Keep state-message throttling independent from issue refresh scheduling and retain coalescing under rapid event bursts.
- Add browser WebSocket liveness handling with a bounded heartbeat or refresh probe, pong/data freshness tracking, stale connection closure, reconnect backoff, and immediate state/issues backfill after reconnect.
- Prevent overlapping reconnect timers and duplicate sockets; clean timers on close/reconnect/page teardown.
- Surface Reconnecting or stale status rather than leaving Connected on a non-delivering socket.
- Preserve authenticated ws/wss URL behavior and console transcript backfill.

Relevant code: oompah/server.py observer and WebSocket broadcast functions, oompah/templates/dashboard.html connectWebSocket, and dashboard/WebSocket lifecycle tests.

Required tests:
- A state-only notification immediately followed within the throttle window by an issue-changing notification still schedules exactly one issues broadcast containing the fresh board snapshot.
- Rapid issue changes are coalesced without being lost.
- Browser heartbeat detects a non-responsive connection, closes it, reconnects once, and requests/backfills current state and issues.
- Normal inbound traffic keeps the connection alive; explicit close/error paths do not create duplicate reconnects.
- Existing authenticated WebSocket bootstrap, console reconnect, and Granian fan-out tests remain green.

Acceptance criteria:
- Task status, agent assignment, Needs Human, and alert-related board changes appear without browser reload.
- No issue-changing notification can be dropped solely because a state-only message was recently broadcast.
- A dead connection self-recovers within a bounded interval and visibly reports reconnecting state.
- Focused dashboard/WebSocket tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 00:37
---
Operator claimed this live dashboard-refresh regression for direct implementation.
---
author: oompah
created: 2026-08-02 00:39
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 00:39
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 00:40
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 55, Tool calls: 28
- Tokens: 146 in / 4.6K out [4.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 36s
- Log: OOMPAH-690__20260802T003910Z.jsonl
---
author: oompah
created: 2026-08-02 00:40
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 00:41
---
Focus: Callback Auth Validation Specialist
---
<!-- COMMENTS:END -->
