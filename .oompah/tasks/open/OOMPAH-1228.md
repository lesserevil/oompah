---
id: OOMPAH-1228
type: task
status: Open
priority: null
title: Allow landed deleted-source submissions through validation commit guard
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T09:30:46.069410Z'
updated_at: '2026-08-13T09:37:23.474109Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 8da572d7-f464-44ad-807b-2ac8e3eca989
  request_fingerprint: 6799d0fc8aba0cd3563e447d80c1c8678cd66345d3a948da7c52f7f343ecb250
oompah.lifecycle_revision: 1
---
## Summary

Bug observed live after deploying OOMPAH-1226. TRICKLE-140's accepted head is exactly contained in GitLab main and its source branch was normally deleted after merge. Reconciliation now correctly schedules validation_submission instead of implementation_recovery, but Orchestrator._validation_submission_transition_conflict requires project_store.remote_branch_head(source) == expected_head at commit time. That invariant cannot hold for the proven landed/deleted-source route, so the validation transition repeatedly fails (live rows 16019/16020) and retry exhaustion strands the task in In Progress. Scope: extend the commit-time mutation guard to accept either an exact current source head or exact immutable containment of the accepted head in the stable accepted target branch; retain project/task/head/target/owner fencing and fail closed when source/target evidence is unavailable or changed. Ensure guard exceptions are logged with safe context before returning transition.mutation_guard_failed so future failures are diagnosable. Add tests reproducing deleted-source+target-contained success, deleted-source+not-contained failure, source-advanced failure, target mismatch/unavailable failure, and the full validation transition path. Acceptance: TRICKLE-140 advances naturally from In Progress without an implementer, validation retry growth stops, alerts clear after a successful successor generation, focused transition/workflow tests and hosted Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 09:31
---
Claimed directly for live TRICKLE-140 recovery. OOMPAH-1226 stopped implementation recovery churn (646 historical rows; no additions after 09:23:39) and routed the task into validation_submission. The commit guard then exhausted because it still requires the deleted source ref instead of accepting exact target containment. Implementing the missing commit-time route now.
---
author: oompah
created: 2026-08-13 09:37
---
Implementation pushed as PR #857. The commit-time validation guard accepts exact target containment only when the accepted source ref is absent; source advancement, target drift, missing/non-contained target proof, and owner/assignment changes remain blocked. Guard exceptions now retain a traceback in logs. Focused transition/runtime verification: 450 passed. Hosted gates are running.
---
<!-- COMMENTS:END -->
