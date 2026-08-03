---
id: OOMPAH-724
type: task
status: Backlog
priority: null
title: Fence accepted submissions against post-handoff worktree mutation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T15:25:39.369981Z'
updated_at: '2026-08-03T15:30:55.126085Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction: EXOCOMP-172 submitted clean pushed head 113a7337cbb9efa1b07b3f23c627b477bc9ac7a5. After submission acceptance but before worker retirement completed, the managed worktree acquired a formatter-only change. Worker cleanup correctly preserved it as recovery checkpoint 9390df29c8ddb92abd66847b7767b37104313918. Integration then rejected the task because local HEAD differed from the published submitted head, moved the task back to implementation, and required another agent even though the preservation system prevented data loss.

Implementation scope:
- Make the transition from accepted worker submission to worker retirement and integration eligibility generation-fenced and race-free.
- Revoke further task mutation authority when submission is accepted, quiesce the complete managed process tree, and perform a final branch/head/cleanliness check before enqueuing integration.
- If task-owned changes appear after the accepted evidence, preserve them exactly once and reopen the task with explicit recovery context before integration is attempted; do not emit a transient Ready row that can only fail with worktree_recovery.
- Define a safe bounded path for a clean Oompah-created recovery checkpoint that is a linear descendant of the accepted pushed head. Do not silently publish or integrate unreviewed content, and never reset or discard the snapshot.
- Preserve same-head resubmission idempotency, authority-generation fencing, cleanup safety, and cross-task isolation.

Relevant code: oompah/server.py submission authority lock and persistence, oompah/orchestrator.py worker exit and submission handoff, oompah/projects.py recovery snapshots, oompah/integration_executor.py worktree recovery checks, and task CLI evidence capture.

Required tests:
- Reproduce EXOCOMP-172 with a clean pushed submit followed by a late tracked formatter change before worker exit.
- Prove integration is not attempted against stale submitted evidence and the task is reopened exactly once with the preserved checkpoint available to the next worker.
- Cover late staged, unstaged, and untracked changes; background child exit; simultaneous submit and teardown; restart recovery; repeat submit; snapshot failure; and no-change normal submission.
- Prove no task content is reset, auto-pushed, or integrated without explicit resubmission.
- Run focused submission, recovery, worker lifecycle, integration executor, and authority-race suites plus make test.

Acceptance criteria:
- An EXOCOMP-172-style late mutation cannot churn through Ready to Integrate and an integration worktree-recovery failure.
- Accepted evidence becomes integration-eligible only after the worker generation is quiescent and the final worktree state matches it.
- Late work remains durably recoverable and receives one actionable retry without data loss or duplicate dispatch.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

