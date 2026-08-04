---
id: OOMPAH-751
type: bug
status: Open
priority: 1
title: Do not poison task completion when advisory peer authorization changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T01:46:13.265163Z'
updated_at: '2026-08-04T01:48:31.412930Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2f733d40f8ef116556b2dfd652bf5659d4526315156e002142c846059300d610
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 228aa7a7-5443-41fe-a9ec-a02306c2c74f
  claim_owner: 1c23f4c6-4c13-43af-86f6-1edf14468b70
  claimed_at: '2026-08-04T01:48:19.602196+00:00'
  claim_expires_at: '2026-08-04T02:18:19.602196+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4f0597bb-1ee4-4047-967c-ed64442c8041
---
## Summary

Triggered by: OOMPAH-746

Live reproduction: OOMPAH-746 completed and pushed repair head 3ed0f959, then sent an advisory coordination message to OOMPAH-734. Between peer discovery and send, the dynamic suggested-peer set no longer authorized that recipient. Orchestrator.coordination_send raised PermissionError, but the task-handoff endpoint converted it to HTTP 500, recorded an actionable handoff failure, and worker-exit reconciliation moved OOMPAH-746 to Needs Human before its own successful work could be submitted. OOMPAH-689 covers expected read-only peer denials, not this coordination-send race. Implementation scope: treat a recipient that is no longer suggested as an expected fail-closed coordination policy result rather than an assigned-task handoff or authentication failure; return a structured non-500 response; preserve the worker capability for its own comment and submit operations; and ensure optional coordination cannot poison successful completion. Either authorize against a stable peer grant or make send-time revalidation explicitly race-safe and idempotent. Preserve strict denial and non-disclosure for arbitrary recipients, cross-project sends, wrong or expired tokens, and mutations outside the granted task. Relevant code: task-handoff coordination-send handling in oompah/server.py, Orchestrator.coordination_send and peer derivation, task_handoff failure recording, worker-exit reconciliation, and auth-health classification. Required tests: peer suggested then removed before send; recipient transitions from running to Ready or In Review; durable fallback to a non-running still-authorized peer; arbitrary recipient; cross-project recipient; expired token; advisory send failure followed by successful own-task submit; restart and idempotency. Acceptance criteria: the race cannot return a generic 500, degrade worker auth health, prevent own-task submission, or move completed work to Needs Human; unauthorized disclosure and mutation remain impossible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 01:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 01:48
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
