---
id: OOMPAH-937
type: bug
status: Open
priority: 1
title: Project current exhausted jobs as actionable liveness failures
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-09T07:29:03.390818Z'
updated_at: '2026-08-09T07:29:36.208727Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-931

Production after OOMPAH-931 reports workflow_jobs.current_states.exhausted=104 while the same affected tasks are projected by workflow liveness as disposition=retry_scheduled, alert_level=info, action_required=false, and unexplained divergence. The universal controller currently recognizes stored exhaustion only when the schedule cursor decision revision exactly equals the newly evaluated decision revision; ordinary evidence/reassessment revision changes can therefore mask an exhausted generation that remains authoritative in the store current-state projection. Implement one authoritative per-task current-generation exhaustion lookup shared with workflow job health, and make liveness projection classify that condition as retry.exhausted/action_required until a distinct replacement generation actually owns recovery. Preserve historical exhausted ledger rows as non-actionable when superseded, fail closed on ambiguous cursor/generation state, and prevent repeated reevaluation from silently downgrading current exhaustion. Add regression tests covering an exhausted integration landing refresh followed by evidence/reassessment revision changes, historical superseded exhaustion, a queued replacement generation, restart/persistence, current_states parity, and state/API alert projection. Acceptance: every current_states.exhausted job maps to an actionable task/liveness explanation or an explicitly documented non-task system owner; no current exhaustion is shown as normal retry activity; superseded historical exhaustion remains non-actionable; focused tests and the complete branch gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

