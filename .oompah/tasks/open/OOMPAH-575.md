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
updated_at: '2026-07-30T13:32:58.066689Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 161ed12e153fe52f6201c32494aa9699b3e730445a34d9fc929cf8f3982e45d4
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: ea370a01-8ad7-4517-9047-76284e88002a
  claim_owner: 42623072-9e4e-4956-a81f-a5c79aedc624
  claimed_at: '2026-07-30T13:32:52.576051+00:00'
  claim_expires_at: '2026-07-30T14:02:52.576051+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 173e46e2-0e50-49a4-b448-5cf9616e314b
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 13:32
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 13:32
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
