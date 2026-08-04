---
id: OOMPAH-813
type: task
status: Backlog
priority: null
title: Fence revoked accepted-submission worker exits with the resolved project
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T23:50:36.091912Z'
updated_at: '2026-08-04T23:50:36.091912Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Bug reproduction: in Orchestrator._on_worker_exit, the accepted_submission_record && revoked path calls _handle_revoked_submission_exit(project_id=project_id, ...) before project_id is assigned later in the method. A revoked worker that has already submitted therefore raises NameError instead of executing the safety recovery path. This predates the durable-domain stack but is present in its exact review head and Ruff reports F821. Implementation scope: resolve the project identity before any revoked-submission branch, preserve exact project/task/run authority fencing, and keep later worker-exit handling on the same resolved project without shadowing or cross-project fallback. Relevant code: oompah/orchestrator.py _on_worker_exit and _handle_revoked_submission_exit. Required tests: exercise _on_worker_exit itself (not only the helper) with an accepted submission plus revoked authority; assert no NameError, exact project is forwarded, cross-project records cannot be handled, and ordinary non-revoked exit behavior is unchanged. Run focused worker-exit/submission-fencing suites and terminal mutation scan. Acceptance: every revoked accepted-submission exit deterministically reaches the project-scoped recovery handler and never reads an uninitialized identity.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

