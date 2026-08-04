---
id: OOMPAH-810
type: task
status: Open
priority: null
title: Return completed auditor command results without stranding the ACP session
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-768
labels: []
assignee: null
created_at: '2026-08-04T22:01:00.091773Z'
updated_at: '2026-08-04T22:05:35.718743Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-810
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: eb5988541933bb61ffa8da942cca688895a4da328725747475570afc6aaaac22
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: b59dc677-6a0b-4162-8d24-a943f0e4d2b2
  claim_owner: f75f2e47-c230-48b7-9af8-09eea50f8e9b
  claimed_at: '2026-08-04T22:04:38.925297+00:00'
  claim_expires_at: '2026-08-04T22:34:38.925297+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 17d15d58-120f-4ece-b24f-b90375a78827
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-810
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-810
  base_branch: epic-OOMPAH-763
  base_sha: f1e7925b7263f980517f943291102c8c83335ed2
  updated_at: '2026-08-04T22:05:30.389256+00:00'
---
## Summary

Live reproduction on 2026-08-04: OOMPAH-793 audit audit-8b63c91a6c05 / attempt-7e65eccae518 invoked the approved make test-serial command at 21:44:04. The pytest and shell children remained live and were correctly protected while running, then exited around 21:56. The ACP JSONL never emitted a tool_result after the permission grant, RunningEntry retained the provider with no command child, and the server detected a stall at 21:58:46 before forced shutdown. This is distinct from merged OOMPAH-648 (do not false-stall a live child), OOMPAH-719 (bound oversized run_command output), and OOMPAH-612 (submit_audit_result same-loop deadlock): the approved command finished, but completion/output never returned to the auditor.\n\nImplementation scope:\n- Trace the ACP run_command subprocess completion, ToolLivenessMonitor cleanup, CommandOutputStore truncation/paging, MCP response bridge, and provider transport after a large configured Makefile command exits.\n- Guarantee exactly one bounded tool_result reaches the session promptly after process exit, regardless of output size, pass/fail exit, cancellation, or concurrent stall inspection; expose an opaque continuation ID without synchronously serializing unbounded output.\n- Clear tool-liveness ownership only after the result is durably deliverable, and distinguish running, result_pending, result_delivered, and provider_stalled in state metrics.\n- If result delivery cannot complete within a bounded deadline, retire/retry the audit once with a precise transport classification; never leave a provider visible indefinitely or repeat an expensive successful validation blindly when durable command evidence can be reused safely.\n- Preserve read-only audit authority, output redaction, per-session isolation, command deadlines, independent-candidate rotation, and terminal exact-head fencing. Coordinate with OOMPAH-781 durable terminal-audit cutover instead of adding another process-local lifecycle.\n\nRequired tests:\n- An approved command emits more than 1 MB, exits successfully after a silent interval, and produces one bounded tool_result plus pageable continuation without provider-private paths.\n- Passing and failing exits, child exit concurrent with stall scan, cancellation, provider disconnect, and restart each clear liveness and yield exactly one durable outcome/retry.\n- A completed command cannot remain RunningEntry-only with no child and no ACP event beyond the result-delivery deadline.\n- Reproduce OOMPAH-793 with make test-serial-shaped output and prove the auditor can submit its verdict and exit normally.\n- Focused ACP/tool-liveness/auditor tests and make test pass.\n\nAcceptance criteria: once an approved auditor command exits, the ACP session receives its bounded result or a precise recoverable transport failure within a fixed deadline; no completed command strands In Validation work or consumes a provider slot; OOMPAH-793-style recovery does not require operator mutation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 22:05
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 22:05
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
