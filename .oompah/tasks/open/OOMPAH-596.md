---
id: OOMPAH-596
type: bug
status: Open
priority: 1
title: Rearm conflict repairs after recoverable agent infrastructure failure
parent: OOMPAH-587
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:15:26.248587Z'
updated_at: '2026-07-30T14:18:58.949202Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Fix integration repair lifecycle so a rebase-conflict row is not left permanently blocked when its repair worker exits because of task-auth, provider, sandbox, or other recoverable infrastructure failure. Preserve the real conflict and attempt history, retry only after the prerequisite health condition changes or bounded backoff expires, and transition exhausted repairs to an explicit needs-human state with exact safe instructions. Apply the recovery path to OOMPAH-484 and OOMPAH-487 after scoped task auth is live. Relevant files include integration queue/executor repair dispatch, orchestrator landing/retry logic, watchdog state, and queue API/UI summaries.

Tests

Cover real conflict plus 401, provider failure, successful retry, repeated failure/backoff, restart, no duplicate workers, and needs-human exhaustion. Run focused integration/orchestrator tests and make test.

Acceptance criteria

Recoverable infrastructure failure cannot silently strand a conflict row; OOMPAH-484 and OOMPAH-487 either integrate after repair or show an explicit unresolved conflict requiring a named operator action.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
<!-- COMMENTS:END -->
