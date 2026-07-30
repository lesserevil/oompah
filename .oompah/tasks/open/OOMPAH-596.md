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
updated_at: '2026-07-30T15:30:52.356059Z'
work_branch: epic-OOMPAH-587--task-OOMPAH-596
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b8c9779d72e8d10e89d53ba9eed3f6602095a5255ac360e48817df156b151940
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4a885e64-8f5d-4dc3-97c3-b3c7898c25db
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T15:30:42.587556+00:00'
  claim_expires_at: '2026-07-30T16:00:42.587556+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 64effcd9-d21e-44c7-b1f9-478039bcb550
oompah.work_branch: epic-OOMPAH-587--task-OOMPAH-596
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-587--task-OOMPAH-596
  base_branch: epic-OOMPAH-587
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T15:30:50.376910+00:00'
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
author: oompah
created: 2026-07-30 15:30
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:30
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
