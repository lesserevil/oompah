---
id: OOMPAH-575
type: task
status: Open
priority: null
title: Propagate scoped task CLI auth to Codex agent sessions
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T02:15:25.255613Z'
updated_at: '2026-07-30T13:31:05.450176Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Ensure service-launched Codex repair/development sessions receive working scoped task-CLI authentication for their assigned project/task. A repair session for OOMPAH-479 could use its repository tools but plain `oompah task view` returned HTTP 401, while the operator shell and MCP-backed session were authenticated. Trace task-handoff credential creation and environment propagation through the Codex ACP launch path; preserve least-privilege assignment scoping and avoid exposing server-wide credentials. Relevant files include oompah/task_handoff.py, oompah/acp_backends/codex.py, oompah/acp_session.py, and server/orchestrator launch wiring.

Tests

Add a Codex-session regression proving an assigned agent can view, comment on, and submit only its assigned task using the CLI-provided environment; assert missing/expired tokens fail closed and unrelated tasks remain unauthorized. Run focused task-handoff/ACP tests and the configured full Makefile gate.

Acceptance criteria

A service-launched Codex agent can execute the documented `oompah task` workflow for its own assigned task without operator credentials, receives no broader tracker authority, and no 401 occurs in the normal launch path.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

