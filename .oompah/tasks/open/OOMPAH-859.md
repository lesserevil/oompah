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
updated_at: '2026-08-06T11:43:01.150187Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression observed 2026-08-06 while OOMPAH-835/OOMPAH-836 auditors were queued behind the exact OOMPAH-837 quality gate: /api/v1/state emitted terminal_audit_health:backlog_age with detail 'oldest pending audit is 3695s old across 0 pending audit(s)'. This is internally contradictory and consumes dashboard alert space even though no dispatchable audit is pending. Implementation scope: trace TerminalAuditHealth aggregation/projection so pending_count, stale_pending_count, and oldest_pending_age_seconds come from the same current authoritative record set/generation; suppress backlog_age whenever pending_count is zero; preserve truthful informational recovery state for genuinely stale pending audits; clear cached age/stale facts after the last pending record retires; cover active auditors and validation-resource waiters separately from pending audit backlog. Relevant files: oompah/terminal_audit_health.py, terminal audit observability/enforcement state projection, orchestrator state assembly, dashboard alert tests. Required tests: reproduce non-null stale age + stale_pending_count with zero pending_count and assert no alert; last pending audit completion clears all backlog facts in the same authoritative update; queued/running auditors do not produce a zero-pending backlog warning; genuinely stale pending work still produces one informational, non-operator-action alert under OOMPAH-795 semantics; restart/snapshot generation cannot combine old age with new count. Acceptance: no state payload can emit backlog_age with pending_count=0, all displayed counts/ages are generation-consistent, and focused terminal-audit health/observability/state tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

