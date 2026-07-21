---
id: OOMPAH-306
type: bug
status: In Progress
priority: 1
title: Reconcile dashboard task state with canonical state-branch records
parent: null
children: []
blocked_by: []
labels:
- focus-complete:frontend
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T16:27:56.291769Z'
updated_at: '2026-07-21T16:48:17.497572Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 8aab720d-556d-4d1d-9737-59eb1d9583d8
oompah.task_costs:
  total_input_tokens: 1609925
  total_output_tokens: 7808
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1609925
      output_tokens: 7808
      cost_usd: 0.0
  runs:
  - profile: deep
    model: unknown
    input_tokens: 1130693
    output_tokens: 5898
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:45:36.238592+00:00'
  - profile: default
    model: unknown
    input_tokens: 479232
    output_tokens: 1910
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:48:04.116874+00:00'
---
## Summary

Fix the dashboard/API task-state display when it disagrees with Oompah’s canonical state branch.\n\nReproduction: OOMPAH-286 displays as Merged even though the canonical record on oompah/state/proj-14849f1b has status=Backlog, parent=OOMPAH-285, and null work_branch, review_url, and merged_at.\n\nRequirements:\n- For state-branch-enabled native projects, every board/list/detail/CLI read must use the current configured state-branch revision, not source-branch files or stale snapshots.\n- Cache keys/invalidation must include project ID, state branch, tracker revision, and task identifier.\n- Board, drawer, API, and CLI must agree on status, parent, branch, review URL, and merged timestamp.\n- If state reads are stale/unavailable, display an explicit indicator; never silently render obsolete state as authoritative.\n- Do not mutate task data to repair this display problem.\n\nTests:\n- Regression fixture where stale source/cache says Merged but state branch says Backlog; all views show Backlog.\n- Checkpoint update invalidates task list/detail caches without restart.\n- Verify per-project isolation and null merged_at cannot render Merged.\n- Verify degraded reads retain no false terminal status.\n\nAcceptance criteria:\n- Dashboard, detail pane, CLI/API, and canonical Markdown agree.\n- A task is Merged only when canonical state records it.\n- Operators can identify stale tracker data.\n- Relevant Makefile tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 16:40
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 16:40
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-21 16:40
---
Understanding: I will trace dashboard task list/detail rendering and its API payloads, then ensure the UI does not present a terminal state when the state-branch read is stale or unavailable. I will add focused regression coverage and hand off any canonical tracker/cache routing work outside frontend scope.
---
author: oompah
created: 2026-07-21 16:41
---
Discovery: dashboard.html fetchIssues() discards the server's X-Oompah-Issues-Stale header, while board/detail render the returned fields as authoritative. server.py snapshot cache is keyed only as issues:all and detail:{project}:{identifier}:actor, so canonical state-branch revision routing/invalidation is backend work. Frontend scope: render an explicit accessible stale-state warning from API freshness and preserve it across board refreshes.
---
author: oompah
created: 2026-07-21 16:42
---
Implementation (frontend): added an accessible task-state freshness banner in dashboard.html. fetchIssues() now consumes X-Oompah-Issues-Stale, warns on stale or failed reads, and clears only on a fresh response. Added tests/test_dashboard_state_read_warning.py covering the banner and stale/unavailable behavior.
---
author: oompah
created: 2026-07-21 16:42
---
Verification: git diff --check passed. make test could not start because the environment's astral-uv launcher failed creating a transient DBus scope (Makefile .venv/.uv-setup, exit 46), before pytest collection. Frontend regression test is included but has not run in this environment.
---
author: oompah
created: 2026-07-21 16:45
---
Focus handoff: frontend\n\nOutcome: added an accessible dashboard warning when the issues REST response is stale or unavailable, preventing silent presentation of obsolete board state.\n\nFiles/evidence: oompah/templates/dashboard.html now consumes X-Oompah-Issues-Stale; tests/test_dashboard_state_read_warning.py covers stale/failure banner behavior. git diff --check passes. make test is blocked before collection by astral-uv DBus transient-scope error. Commit/push is also blocked because the shared git worktree admin directory is read-only while creating index.lock; changes remain uncommitted in this worktree.\n\nRemaining work/risks: server.py snapshot and detail cache keys lack state branch/tracker revision; WebSocket payloads do not include freshness; canonical state reads and cache invalidation must be corrected so no stale terminal state is emitted.\n\nRecommended next focus: backend.
---
author: oompah
created: 2026-07-21 16:45
---
Agent completed successfully in 314s (1136591 tokens)
---
author: oompah
created: 2026-07-21 16:45
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 30
- Tokens: 1.1M in / 5.9K out [1.1M total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 14s
- Log: OOMPAH-306__20260721T164025Z.jsonl
---
author: oompah
created: 2026-07-21 16:45
---
Focus handoff from `frontend` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 16:46
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 16:47
---
Understanding (duplicate screening): I will search existing native task records for prior work on state-branch canonical task reads, cache invalidation, and stale dashboard/API state, then read any candidates fully before deciding whether OOMPAH-306 is a duplicate.
---
author: oompah
created: 2026-07-21 16:47
---
Discovery (duplicate screening): No confirmed duplicate. Reviewed the state-branch epic OOMPAH-253 and its implementation tasks OOMPAH-255, OOMPAH-257, OOMPAH-258, and OOMPAH-260, plus current state-branch-error task OOMPAH-282. OOMPAH-256 is the closest related completed work (state-branch tracker read/write routing); OOMPAH-257 covers checkpoint coalescing. Neither addresses stale server issue/detail cache keys by state-branch tracker revision, nor requires board/drawer/API/CLI agreement and degraded-read terminal-state safety. OOMPAH-306 is distinct.
---
author: oompah
created: 2026-07-21 16:47
---
Focus handoff: duplicate_detector\n\n1. Outcome: no duplicate confirmed; OOMPAH-306 remains the canonical task for stale state-branch task displays.\n\n2. Evidence: searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for canonical-state, state-branch reads, stale snapshots, cache invalidation, and tracker revisions; read OOMPAH-253, OOMPAH-255, OOMPAH-257, OOMPAH-258, OOMPAH-260, and OOMPAH-282. The prior frontend handoff identifies dashboard.html freshness handling already added, while server.py cache revision routing remains outstanding.\n\n3. Remaining work/risks: implement canonical state-branch revision reads and revision-aware cache keys/invalidation for list/detail/API/CLI; ensure degraded reads cannot emit false terminal status; add the required cross-view regression coverage.\n\n4. Recommended next focus: feature (backend tracker/cache implementation).
---
author: oompah
created: 2026-07-21 16:48
---
Agent completed successfully in 73s (481142 tokens)
---
author: oompah
created: 2026-07-21 16:48
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 22
- Tokens: 479.2K in / 1.9K out [481.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 13s
- Log: OOMPAH-306__20260721T164654Z.jsonl
---
author: oompah
created: 2026-07-21 16:48
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 16:48
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:48
---
Focus: Test Engineer
---
<!-- COMMENTS:END -->
