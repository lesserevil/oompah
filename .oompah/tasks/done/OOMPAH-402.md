---
id: OOMPAH-402
type: task
status: Done
priority: null
title: Advance focus after completed agent handoffs
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T05:27:02.143073Z'
updated_at: '2026-07-22T05:31:30.954315Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix scheduler behavior where a normally completed agent handoff is retried as unfinished and the next run re-selects the same non-implementation focus. Use task comments and/or persisted focus state to recognize completed focus handoffs, advance to the next applicable focus, and avoid retrying solely because the task remains non-terminal when the handoff records productive completion. Cover OOMPAH-339's repeated Test Engineer routing with regression tests. Acceptance: a completed handoff advances focus; a no-op completion still retries; OOMPAH-339-like implementation tasks do not loop through completed investigation/test foci; relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:31
---
Implemented and verified two scheduler fixes: (1) a durable Focus handoff comment now backfills its focus-complete label and advances focus instead of falling into completed-without-closing retries; (2) Test Engineer no longer wins solely from a generic Tests acceptance section, while explicit test routing and test-oriented titles still select it. Added regression coverage and ran make test.
---
author: oompah
created: 2026-07-22 05:31
---
Fixed handoff retry loops and test-focus preemption; added regression coverage; make test passed.
---
<!-- COMMENTS:END -->
