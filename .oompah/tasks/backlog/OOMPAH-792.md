---
id: OOMPAH-792
type: task
status: Backlog
priority: 1
title: Run all historical systemic incidents as full-stack workflow scenarios
parent: OOMPAH-767
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:59:19.563806Z'
updated_at: '2026-08-04T13:59:19.563806Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Use the shared incident corpus to build full-stack scenarios spanning fact collectors, evaluator, job ledger/worker, transition service, native tracker, Git, and UI projection for OOMPAH-562/731/732/739/748/749/751. Avoid mocking the exact boundary whose composition caused the incident. Verify both safety and bounded natural recovery, including server restart and event duplication. Acceptance: every historical workaround scenario progresses without manual status/queue/branch mutation and produces the same reason in executor and UI.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

