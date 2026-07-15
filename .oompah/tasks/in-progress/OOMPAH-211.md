---
id: OOMPAH-211
type: feature
status: In Progress
priority: 0
title: Deliver new task comments to running agents
parent: null
children: []
blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-07-15T20:52:07.206772Z'
updated_at: '2026-07-15T21:37:22.031815Z'
work_branch: OOMPAH-211
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/420
review_number: '420'
merged_at: null
oompah.agent_run_id: a457b89e-fabb-4782-b814-e1a9b7752582
oompah.task_costs:
  total_input_tokens: 208
  total_output_tokens: 5867
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 208
      output_tokens: 5867
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 53
    output_tokens: 1863
    cost_usd: 0.0
    recorded_at: '2026-07-15T20:57:17.232280+00:00'
  - profile: default
    model: unknown
    input_tokens: 155
    output_tokens: 4004
    cost_usd: 0.0
    recorded_at: '2026-07-15T21:25:45.388290+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/420
oompah.review_number: '420'
oompah.work_branch: OOMPAH-211
oompah.target_branch: main
---
## Summary

Triggered by: OOMPAH-210

When a comment is added to a task with an active agent run, deliver it into that agent's live context rather than only exposing it on a future dispatch. Define ordering, idempotency, audit logging, retry behavior, and graceful fallback for providers that cannot accept mid-run messages. Add unit and integration tests proving a running agent receives a newly posted task comment exactly once.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-15 20:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-15 20:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-15 20:55
---
Understanding: OOMPAH-211 asks for delivering new task comments to running agents mid-run. Triggered by OOMPAH-210. My role is Duplicate Investigator — I will search for existing tasks covering the same ground before any implementation begins. Searching now for candidate duplicates.
---
author: oompah
created: 2026-07-15 20:56
---
Discovery: OOMPAH-211 is NOT a duplicate. Searched all task states (in-progress, done, archived, merged), plans/, docs/, README.md and WORKFLOW.md for tasks covering: deliver/inject task comments to running agents mid-run, live context injection, mid-flight messages, human-in-loop injection, idempotent comment delivery. No existing task or plan covers this scenario. OOMPAH-210 (the trigger) is about GitHub check-run 403 errors — a completely different topic. This feature request is genuinely new and requires backend feature implementation: comment-delivery pipeline to active agent runs, ordering/idempotency guarantees, audit logging, retry behavior, provider fallback, and unit/integration tests.
---
author: oompah
created: 2026-07-15 20:56
---
HANDOFF to feature agent: Duplicate investigation complete — this is a NEW feature, not a duplicate. No existing task covers delivering task comments to running agents mid-run. The implementation requires: (1) A mechanism to detect when a task has an active agent run, (2) A comment-delivery pipeline to inject new task comments into the live agent context, (3) Ordering and idempotency guarantees (exactly-once delivery), (4) Audit logging of delivery attempts, (5) Retry behavior on transient failures, (6) Graceful fallback for providers that cannot accept mid-run messages, (7) Unit and integration tests proving a running agent receives a newly posted task comment exactly once. Relevant codebase areas to explore: oompah/orchestrator.py (agent dispatch/run lifecycle), oompah/agents.py or similar (active run tracking), any ACP/SDK integration layers. Plans to read: plans/acp-agent.md, plans/acp-backends.md, plans/agent-watcher.md for context on agent run lifecycle.
---
author: oompah
created: 2026-07-15 20:57
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 39
- Tokens: 53 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 31s
- Log: OOMPAH-211__20260715T205451Z.jsonl
---
author: oompah
created: 2026-07-15 20:57
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-15 20:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-15 20:57
---
Understanding: Previous duplicate investigation confirmed this is a NEW feature. I am now the feature agent implementing: (1) comment-delivery pipeline to inject new task comments into live agent context, (2) ordering/idempotency guarantees, (3) audit logging, (4) retry behavior, (5) graceful fallback for providers that cannot accept mid-run messages, (6) unit and integration tests for exactly-once delivery. Starting codebase exploration now.
---
author: oompah
created: 2026-07-15 21:05
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-15 21:05
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-15 21:12
---
Understanding: Implementing mid-run comment delivery for running agents. Architecture: (1) Add asyncio.Queue per running ACP session to Orchestrator; (2) Extend ClaudeAcpBackendSession.run_turn() to consume injected comments at each ResultMessage boundary (multi-turn injection within the same SDK session); (3) Add deliver_comment_to_running_agent() to Orchestrator with idempotency tracking and audit logging; (4) Hook into api_add_comment in server.py to trigger delivery; (5) Graceful fallback for CLI/API workers (no queue → comment available on next dispatch). Tests: unit tests for delivery, idempotency, multi-turn injection, and fallback. Starting implementation now.
---
author: oompah
created: 2026-07-15 21:24
---
Discovery: Found the key integration points: (1) AcpAgentSession/ClaudeAcpBackendSession in acp_agent.py + acp_backends/claude.py — the Claude SDK drives multi-turn conversations; after each ResultMessage we can inject new turns via client.query(). (2) Orchestrator._run_acp_worker() creates the session and is the right place to attach a per-run comment queue. (3) api_add_comment in server.py is the main entry point for human-posted comments. (4) handle_github_issue_intake_webhook in github_intake_bridge.py handles GitHub comments. Implementation: structuring the ClaudeAcpBackendSession run_turn() as a while-True outer loop that checks for pending comments at each turn boundary.
---
author: oompah
created: 2026-07-15 21:25
---
Implementation: Changed 6 files, added 2 new files. Key changes: (1) ClaudeAcpBackendSession.run_turn() restructured with a while-True outer loop — after each ResultMessage, drains comment_queue and injects pending comments as new SDK turns. (2) Orchestrator.deliver_comment_to_running_agent() added: resolves identifier→issue_id, idempotency check on comment_id, FIFO asyncio.Queue enqueue, audit log. (3) _run_acp_worker() creates and registers per-run asyncio.Queue; unregistered in finally. (4) server.py api_add_comment hook: non-oompah comments trigger delivery. (5) github_intake_bridge.py: _deliver_github_comment_to_agent() helper called on newly imported GitHub comments. (6) plans/comment-delivery.md: design doc with Mermaid sequence diagram.
---
author: oompah
created: 2026-07-15 21:25
---
Verification: All 28 new tests pass (tests/test_comment_delivery.py). Pre-existing tests unaffected: test_acp_agent.py (42 tests), test_acp_backends.py (44 tests), test_github_intake_bridge.py (56 tests), test_orchestrator_handlers.py all pass. Full suite: 8915 passed, 36 skipped, 3 pre-existing failures in test_dashboard_release_delivery_ui.py (unrelated). Branch pushed: OOMPAH-211. Guarantees delivered: ordering (FIFO), idempotency (comment_id dedup), exactly-once delivery within a run, audit logging, retry via tracker on next dispatch, graceful fallback for CLI/api_agent workers.
---
author: oompah
created: 2026-07-15 21:25
---
Completion: OOMPAH-211 delivered. New task comments are now injected into running ACP agent sessions as new turns at each ResultMessage boundary. Entry points: (1) POST /api/v1/issues/{id}/comments for native tasks, (2) GitHub webhook comment sync. Guarantees: FIFO ordering, comment_id idempotency, exactly-once per run, audit log, graceful fallback for non-ACP workers. 28 unit+integration tests. Design doc: plans/comment-delivery.md.
---
author: oompah
created: 2026-07-15 21:25
---
Implemented mid-run comment delivery: new task comments injected into running ACP agent sessions as new turns at each ResultMessage boundary. Added deliver_comment_to_running_agent() to Orchestrator, per-run asyncio.Queue in _run_acp_worker, multi-turn injection loop in ClaudeAcpBackendSession.run_turn(), server/github intake hooks, idempotency/audit/fallback. 28 new tests, design doc in plans/comment-delivery.md.
---
author: oompah
created: 2026-07-15 21:25
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 97
- Tokens: 155 in / 4.0K out [4.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 19m 59s
- Log: OOMPAH-211__20260715T210552Z.jsonl
---
author: oompah
created: 2026-07-15 21:35
---
YOLO: CI tests failed on MR #420. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-07-15 21:35
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-15 21:35
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-15 21:37
---
Understanding: CI failures are 3 pre-existing test failures in test_dashboard_release_delivery_ui.py::TestSelection — dashboard was refactored so _rdiToggleSHA now delegates to _rdiToggleSHAs (shared helper), but tests still check the body of _rdiToggleSHA for the add/delete/updateActionBar calls. Fix: update the 3 tests to check the _rdiToggleSHAs body instead. No change to the feature code.
---
<!-- COMMENTS:END -->
