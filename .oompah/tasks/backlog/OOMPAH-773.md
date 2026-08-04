---
id: OOMPAH-773
type: task
status: Backlog
priority: 1
title: Define stable workflow reason codes and liveness SLOs
parent: OOMPAH-764
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:58:42.900744Z'
updated_at: '2026-08-04T13:58:42.900744Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Define a versioned reason-code taxonomy and measurable SLO contract for Open, In Progress, Ready to Integrate, In Validation, In Review, recovery, and restart convergence. Specify which conditions are normal/informational versus action_required, the responsible subsystem, evidence fields, reassessment deadline, and operator remedy. Add schema validation and documentation. Required tests: stable serialization, unknown forward-compatible codes, severity mapping, bounded deadline validation, and total coverage of canonical nonterminal statuses. Acceptance: code and UI can communicate why a task is not progressing without message-text parsing; normal recovery never maps to warning; each nonterminal decision has a bounded reassessment policy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

