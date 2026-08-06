---
id: OOMPAH-859
type: task
status: Open
priority: null
title: Suppress impossible terminal-audit backlog alerts with zero pending work
parent: OOMPAH-795
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T11:42:33.128386Z'
updated_at: '2026-08-06T11:43:33.567993Z'
work_branch: epic-OOMPAH-795--task-OOMPAH-859
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7a3ca9a3914926508c6ca850586959ccb6e11cdd495f9c7dec17ab80beb207e3
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 7edc7484-6e66-4c93-912a-a2d6a2f4a2fb
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-06T11:43:17.041581+00:00'
  claim_expires_at: '2026-08-06T12:13:17.041581+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: cba93aa8-ac6a-4a74-a2fc-5ea814afed75
oompah.work_branch: epic-OOMPAH-795--task-OOMPAH-859
---
## Summary

Live regression observed 2026-08-06 while OOMPAH-835/OOMPAH-836 auditors were queued behind the exact OOMPAH-837 quality gate: /api/v1/state emitted terminal_audit_health:backlog_age with detail 'oldest pending audit is 3695s old across 0 pending audit(s)'. This is internally contradictory and consumes dashboard alert space even though no dispatchable audit is pending. Implementation scope: trace TerminalAuditHealth aggregation/projection so pending_count, stale_pending_count, and oldest_pending_age_seconds come from the same current authoritative record set/generation; suppress backlog_age whenever pending_count is zero; preserve truthful informational recovery state for genuinely stale pending audits; clear cached age/stale facts after the last pending record retires; cover active auditors and validation-resource waiters separately from pending audit backlog. Relevant files: oompah/terminal_audit_health.py, terminal audit observability/enforcement state projection, orchestrator state assembly, dashboard alert tests. Required tests: reproduce non-null stale age + stale_pending_count with zero pending_count and assert no alert; last pending audit completion clears all backlog facts in the same authoritative update; queued/running auditors do not produce a zero-pending backlog warning; genuinely stale pending work still produces one informational, non-operator-action alert under OOMPAH-795 semantics; restart/snapshot generation cannot combine old age with new count. Acceptance: no state payload can emit backlog_age with pending_count=0, all displayed counts/ages are generation-consistent, and focused terminal-audit health/observability/state tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 11:43
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
