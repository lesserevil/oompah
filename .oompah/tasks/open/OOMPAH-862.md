---
id: OOMPAH-862
type: task
status: Open
priority: null
title: Prevent terminal auditors from redundantly rerunning authoritative full gates
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T14:20:47.304513Z'
updated_at: '2026-08-06T14:21:51.904587Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-862
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ea3892ed7b4cfc880dc90345a4c9b957196bea269515ae7e63fb268c0e15c60f
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: aaa98e68-86f5-4827-bd69-3fd42d5a6730
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-06T14:21:34.385268+00:00'
  claim_expires_at: '2026-08-06T14:51:34.385268+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 31ffd653-fabf-4646-bbab-1de449aec7c9
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-862
---
## Summary

Live OOMPAH-860 regression on 2026-08-06: the exact accepted head completed the configured 16k-test make test gate successfully, and the terminal auditor then launched make test-serial across the entire suite before rendering its independent verdict. This serializes the only validation lane for a long second full run and delays unrelated accepted repairs without adding missing exact-head evidence. Implementation scope: include authoritative exact-head quality-gate command, result, head SHA, duration, and relevant focused evidence in the terminal-audit prompt/evidence bundle; tell auditors to verify the patch and run only narrowly targeted missing checks when the exact configured gate is already current and passing; keep auditors free to request or run a full gate when evidence is missing, stale, failed, mismatched, or the task specifically requires a distinct execution mode. Add observability distinguishing reused authoritative gate evidence, focused supplemental commands, and auditor-initiated full-suite runs. Relevant code: auditor prompt construction and dispatch in oompah/orchestrator.py and oompah/auditor_dispatch.py, quality-gate evidence lookup, terminal audit telemetry, and Completion Auditor focus instructions. Required tests: a current passing exact gate is embedded and suppresses redundant make test or make test-serial guidance; stale/different-head/failed evidence does not suppress a needed gate; focused warning or race checks remain allowed; telemetry records the decision; restart retains the evidence decision. Acceptance criteria: the OOMPAH-860 sequence reaches an independent terminal verdict without a second full-suite run when the exact accepted head already has a passing configured gate, while fail-closed audit behavior remains intact.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 14:21
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
