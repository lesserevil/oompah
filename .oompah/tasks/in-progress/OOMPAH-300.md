---
id: OOMPAH-300
type: task
status: In Progress
priority: 2
title: Add end-to-end repository-map observability and regression coverage
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-298
- OOMPAH-299
labels: []
assignee: null
created_at: '2026-07-21T15:14:10.495385Z'
updated_at: '2026-07-21T23:59:33.283976Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 7ff0b818-35c7-43c6-a3a0-069888d7829d
---
## Summary

Add API/UI-neutral diagnostics and end-to-end tests proving the complete repository-map workflow. Report per-project index status, analyzed SHA, artifact schema version, generation duration, cache reuse, file/symbol counts, failure reason, and prompt inclusion status. Ensure diagnostics expose metadata only by default, not complete repository source. Exercise a managed-project fixture from sync through state-branch persistence and agent prompt construction.\n\nTests:\n- End-to-end fixture proves first dispatch generates a map, a second dispatch reuses it, and a commit change regenerates it.\n- Verify source/release branches remain unchanged by indexing.\n- Verify timeout, parse failure, and state-branch write failure leave agents runnable with no map.\n- Verify diagnostic responses do not leak full source contents or credentials.\n\nAcceptance criteria:\n- Operators can distinguish generating, fresh, stale, unavailable, and failed states.\n- The full workflow is covered by automated regression tests.\n- Failure behavior is demonstrably safe and non-blocking.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 23:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:59
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
