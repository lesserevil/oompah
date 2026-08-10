---
id: OOMPAH-982
type: bug
status: In Progress
priority: 1
title: Retire implementation recovery when direct owner holds authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T02:54:36.526201Z'
updated_at: '2026-08-10T03:15:17.294820Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-981

Live reproduction on OOMPAH-981: after a supported direct-owner claim became active and the task was correctly In Progress, the durable implementation_recovery job continued invoking dispatch. Dispatch correctly denied it with direct_owner_claim, but the workflow treated that expected ownership fence as a retryable failure, consumed all five attempts, and exhausted. Scope: make implementation recovery recognize an exact current direct-owner claim as successful/superseded recovery ownership instead of attempting scheduler dispatch; retire any stale retry generation without revoking the owner; preserve automatic recovery for truly orphaned tasks and fail closed for expired, mismatched, retirement-pending, or cross-project claims. Relevant code includes implementation recovery revalidation/apply/verify, direct-owner fact projection, retry classification, restart reconstruction, and liveness job authority. Required tests: active exact owner claim produces no dispatch and no retry/exhaustion; claim installed during recovery wins the race; expired/released/replaced claim resumes ordinary recovery; restart with a retained claim converges idempotently; cross-task/project claims do not suppress recovery; and no stale recovery job revokes an ABA replacement. Acceptance: a directly owned In Progress task has no current implementation_recovery retry or exhausted job, zero false operator warning, and ordinary orphan recovery remains bounded; focused tests and the complete project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 02:55
---
Claimed for direct-owner completion from the exact OOMPAH-981 live exhausted recovery generation. A separate implementation branch is being worked in parallel with OOMPAH-981.
---
author: oompah
created: 2026-08-10 03:15
---
The exact direct-owner/recovery race fix is implementation-complete. Focused suites pass (152 tests from implementation workflow coverage); independent review and the complete 19,297-test branch gate are in progress.
---
<!-- COMMENTS:END -->
