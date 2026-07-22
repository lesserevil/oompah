---
id: OOMPAH-359
type: task
status: Done
priority: 1
title: Expose epic branch staleness without synchronization churn
parent: OOMPAH-356
children: []
blocked_by:
- OOMPAH-357
labels: []
assignee: null
created_at: '2026-07-22T01:23:53.416699Z'
updated_at: '2026-07-22T01:30:13.981343Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Update the dashboard/API representation of epic branch state so users can distinguish detected staleness from an approved or in-progress synchronization action. Show the branch relation, staleness details, policy outcome, and actionable reason when relevant.\n\nImplementation scope:\n- Keep stale alerts visible for incomplete epics.\n- Add a clear state/reason for 'observed only; no synchronization scheduled'.\n- For permitted work, display why it was scheduled (PR preparation, conflict, explicit request, or configured threshold).\n- Do not add a control that silently performs automatic synchronization.\n\nTests:\n- API serialization tests for observed-only and action-scheduled states.\n- UI tests for the reason/state display and absence of an automatic-action implication.\n\nAcceptance criteria:\n- Operators can tell why an epic is stale and whether Oompah will act.\n- A stale but incomplete epic is visibly non-actionable by default.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

