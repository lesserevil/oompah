---
id: OOMPAH-741
type: bug
status: Open
priority: 1
title: Classify dashboard facts by current operator actionability
parent: OOMPAH-740
children: []
blocked_by:
- OOMPAH-735
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T22:56:13.861445Z'
updated_at: '2026-08-03T22:57:26.700111Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Implement one structured server-side presentation contract for dashboard alerts and health facts.

Scope:
- Define explicit fields for action_required, severity, lifecycle or recovery state, stable identity, compact summary, sanitized detail, remediation, and active versus recovered status.
- Apply the contract to generic orchestrator alerts, terminal-audit health, branch quality gates, authentication health, repository hygiene, and integration retry alerts.
- Build on OOMPAH-735 for integration recovery rather than duplicating its classifier.
- Treat normal pending or running audits, active quality gates, healthy repository inventory, bounded retries, recovered failures, and intentional policy denials as status or history rather than global warnings.
- Preserve task-local failure evidence and metrics even when a condition is not globally actionable.
- Deduplicate equivalent facts at the snapshot boundary using stable source identity and prefer the highest current severity.
- Ensure recovery deterministically clears or downgrades the actionable fact.

Relevant files: oompah/orchestrator.py, oompah/terminal_audit_health.py, auth and repository health builders, oompah/server.py snapshot construction, and their existing unit tests.

Required tests:
- Each producer emits the structured contract without secrets.
- Normal operating states never become actionable warnings.
- Stale, exhausted, unowned, corrupt, or otherwise blocked states do become actionable.
- Recovery removes or downgrades the alert while retaining metrics and task diagnostics.
- Duplicate producers collapse to one stable fact.
- OOMPAH-735 integration behavior remains covered.

Acceptance criteria:
- The state API gives the frontend an unambiguous actionability decision without parsing message text.
- Every actionable warning describes a current condition requiring operator intervention.
- Historical and automatically recovering failures remain inspectable but do not occupy the global warning surface.
- Focused alert, health, state API, and WebSocket tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

