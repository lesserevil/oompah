---
id: OOMPAH-751
type: bug
status: Backlog
priority: 1
title: Do not poison task completion when advisory peer authorization changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T01:46:13.265163Z'
updated_at: '2026-08-04T01:46:13.265163Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-746

Live reproduction: OOMPAH-746 completed and pushed repair head 3ed0f959, then sent an advisory coordination message to OOMPAH-734. Between peer discovery and send, the dynamic suggested-peer set no longer authorized that recipient. Orchestrator.coordination_send raised PermissionError, but the task-handoff endpoint converted it to HTTP 500, recorded an actionable handoff failure, and worker-exit reconciliation moved OOMPAH-746 to Needs Human before its own successful work could be submitted. OOMPAH-689 covers expected read-only peer denials, not this coordination-send race. Implementation scope: treat a recipient that is no longer suggested as an expected fail-closed coordination policy result rather than an assigned-task handoff or authentication failure; return a structured non-500 response; preserve the worker capability for its own comment and submit operations; and ensure optional coordination cannot poison successful completion. Either authorize against a stable peer grant or make send-time revalidation explicitly race-safe and idempotent. Preserve strict denial and non-disclosure for arbitrary recipients, cross-project sends, wrong or expired tokens, and mutations outside the granted task. Relevant code: task-handoff coordination-send handling in oompah/server.py, Orchestrator.coordination_send and peer derivation, task_handoff failure recording, worker-exit reconciliation, and auth-health classification. Required tests: peer suggested then removed before send; recipient transitions from running to Ready or In Review; durable fallback to a non-running still-authorized peer; arbitrary recipient; cross-project recipient; expired token; advisory send failure followed by successful own-task submit; restart and idempotency. Acceptance criteria: the race cannot return a generic 500, degrade worker auth health, prevent own-task submission, or move completed work to Needs Human; unauthorized disclosure and mutation remain impossible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

