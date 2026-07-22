---
id: OOMPAH-352
type: task
status: In Progress
priority: 2
title: Add stall diagnostics and wedge recovery telemetry
parent: OOMPAH-348
children: []
blocked_by:
- OOMPAH-349
- OOMPAH-350
- OOMPAH-351
labels: []
assignee: null
created_at: '2026-07-22T00:56:40.490026Z'
updated_at: '2026-07-22T00:57:02.067997Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement operator-visible diagnostics for scheduler and HTTP stalls. Capture tick phase, active operation, executor queue depth, and Python thread stacks when a tick exceeds a configurable threshold. Expose recent stall events in GET /api/v1/state and write a bounded diagnostic artifact under ~/.oompah. Avoid secrets and prompt contents.

Tests: trigger a controlled slow operation; assert one bounded diagnostic artifact and sanitized state telemetry are produced, repeated alerts are rate-limited, and normal ticks do not emit artifacts.

Acceptance: an operator can identify the blocking phase and thread stack from the running service after a stall; diagnostics do not themselves block the API; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

