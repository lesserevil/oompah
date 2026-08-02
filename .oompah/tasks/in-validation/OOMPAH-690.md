---
id: OOMPAH-690
type: task
status: In Validation
priority: null
title: Restore reliable automatic dashboard updates
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T00:37:18.141681Z'
updated_at: '2026-08-02T01:07:08.887232Z'
work_branch: OOMPAH-690
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/649
review_number: '649'
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
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-690
  head_sha: cac4b5141dcbe43217f4a3848e6bd7ac226a8f42
  submitted_at: '2026-08-02T00:51:01.811525+00:00'
  updated_at: '2026-08-02T00:51:01.811525+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/649
oompah.review_number: '649'
oompah.work_branch: OOMPAH-690
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-13ffd4016256
    project_id: proj-14849f1b
    task_id: OOMPAH-690
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c9d3b10e69b10f4843eea0560bdad610fe48e89d02695fe47c314c1446d8de65
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T01:07:02.181150+00:00'
  - version: 1
    audit_id: audit-e6ffcaf668af
    project_id: proj-14849f1b
    task_id: OOMPAH-690
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c9d3b10e69b10f4843eea0560bdad610fe48e89d02695fe47c314c1446d8de65
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T01:07:02.181150+00:00'
  attempt_history: []
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
author: oompah
created: 2026-08-02 00:41
---
Understanding: the server currently couples state throttling to issue-refresh scheduling, so a task-changing event can be dropped after a recent state broadcast. I will separate those scheduling paths while preserving coalescing, then add bounded browser heartbeat/freshness detection, guarded reconnect lifecycle, and reconnect backfill with focused regression tests.
---
author: oompah
created: 2026-08-02 00:42
---
Discovery: server.py uses one _last_state_broadcast gate for both state and issue notifications; issue refresh scheduling is below the early return. dashboard.html has a single fixed 2s reconnect timer, no heartbeat/freshness tracking, and only closes on error. Existing tests are concentrated in tests/test_ws_lifecycle.py plus dashboard source-contract suites.
---
author: oompah
created: 2026-08-02 00:44
---
Implementation: moved _throttled_broadcast_issues scheduling ahead of the state throttle, added an application-level ping/pong response, and replaced the dashboard's fixed reconnect path with guarded heartbeat freshness checks, stale closure, bounded backoff, refresh backfill, and pagehide cleanup. Existing console backfill and ws/wss URL construction remain intact.
---
author: oompah
created: 2026-08-02 00:46
---
Verification: focused WebSocket/dashboard suites pass (118 passed, 1 existing Starlette deprecation warning). Coverage now exercises issue refresh after a state-throttled activity event with a fresh issues payload, rapid issue coalescing, application ping/pong, and browser heartbeat/backoff/backfill/pagehide contracts.
---
author: oompah
created: 2026-08-02 00:50
---
Implemented reliable automatic dashboard refresh: issue snapshot broadcasts no longer get dropped by the state throttle, and dashboard WebSockets now use application heartbeats, stale-connection recovery, bounded singleton reconnects, reconnect backfill, and navigation cleanup/revival. Focused dashboard/WebSocket suite: 207 passed. Full project run: 14,857 passed with one unrelated parallel-only watchdog failure; that test passed twice in isolation. make check-secrets passed.
---
author: oompah
created: 2026-08-02 00:51
---
Prevented state throttling from dropping board updates and added WebSocket heartbeat/reconnect/backfill recovery.
---
author: oompah
created: 2026-08-02 00:51
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 36
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 10m 18s
- Log: OOMPAH-690__20260802T004103Z.jsonl
---
author: oompah
created: 2026-08-02 00:58
---
Branch quality gate passed for `cac4b5141dcbe43217f4a3848e6bd7ac226a8f42` using `make test` in 395.0s. Review creation may proceed.
---
author: oompah
created: 2026-08-02 01:07
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-02 01:07
---
YOLO: merged PR #649.
---
<!-- COMMENTS:END -->
