---
id: OOMPAH-943
type: bug
status: Open
priority: 1
title: Persist successful landing refresh facts before job completion
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:32.442706Z'
updated_at: '2026-08-09T09:10:35.036501Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live OOMPAH-761/OOMPAH-762 generation-246 integration_landing_refresh jobs completed with git_ancestry checkpoints, but workflow_landing_facts retained no rows and later generations queued the same landing action again. Scope: make the integration landing action durably persist the exact source/target/revision/result fact in the same fenced success boundary before completing the job; make replay idempotent and ensure publication failures retry rather than report success. Relevant code: integration action backend/controller, workflow_landing_facts store, workflow worker completion/replay. Tests: successful ancestry and patch-equivalence effects survive restart and suppress a replacement action; persistence failure cannot complete; stale lease/revision cannot publish; repeated event is idempotent. Acceptance: a successful refresh is observable by the next fact cut and is not re-enqueued absent evidence change.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

