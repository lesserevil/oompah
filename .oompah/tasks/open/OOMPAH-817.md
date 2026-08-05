---
id: OOMPAH-817
type: bug
status: Open
priority: 1
title: Persist standalone-clone recovery objects before publishing refs
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T01:04:50.363142Z'
updated_at: '2026-08-05T01:06:08.275260Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction during direct-owner takeover of OOMPAH-814 on 2026-08-05: ProjectStore.preserve_worktree_changes created recovery checkpoint 515cbc2c84ef6bf955468534a163b7fc77b33f2a inside the registered standalone task clone, then attempted git update-ref refs/oompah/recovery/... in project.repo_path. The authoritative repo did not contain that standalone clone's new object, so update-ref failed with "trying to write ref ... with nonexistent object 515cbc2..." after the checkpoint had already mutated the task branch. The transition left OOMPAH-814 In Progress with no running worker, retry, quality gate, or owner claim until an operator retried the claim and manually reconciled the checkpoint. Implementation scope: make recovery snapshots durable across both linked worktrees and registered standalone clones by transferring/fetching the exact commit/tree objects into the authoritative repository before publishing the recovery ref, or by storing the ref in the object database that actually owns the checkpoint and making every recovery reader use that same authority. Treat checkpoint creation plus durable ref publication as a fenced transaction: verify the exact object is readable from the chosen recovery authority before reporting success; on transfer/ref failure preserve the task branch and emit an actionable, automatically retryable recovery state without stranding the task. Do not reset, clean, delete, or rewrite the task checkout. Relevant code: oompah/projects.py _worktree_recovery_ref and preserve_worktree_changes/recovery readers; orchestrator owner-takeover/worker-exit recovery handling. Required tests: linked worktree control; separate standalone clone with distinct object database; missing-object update-ref reproduction; interrupted object transfer; retry/idempotence; restart; exact snapshot/ref resolution; dirty and active-operation checkpoints; and proof the task returns to a recoverable owner/scheduler state rather than ownerless In Progress. Acceptance: every reported recovery_ref resolves to snapshot_head in its authoritative repository, recovery is restart-safe and idempotent, and a persistence failure cannot strand a task or destroy its worktree.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

