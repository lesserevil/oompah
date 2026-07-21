---
id: OOMPAH-306
type: bug
status: Backlog
priority: 1
title: Reconcile dashboard task state with canonical state-branch records
parent: null
children: []
blocked_by: []
labels:
- needs:backend
- needs:frontend
assignee: null
created_at: '2026-07-21T16:27:56.291769Z'
updated_at: '2026-07-21T16:27:56.291769Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix the dashboard/API task-state display when it disagrees with Oompah’s canonical state branch.\n\nReproduction: OOMPAH-286 displays as Merged even though the canonical record on oompah/state/proj-14849f1b has status=Backlog, parent=OOMPAH-285, and null work_branch, review_url, and merged_at.\n\nRequirements:\n- For state-branch-enabled native projects, every board/list/detail/CLI read must use the current configured state-branch revision, not source-branch files or stale snapshots.\n- Cache keys/invalidation must include project ID, state branch, tracker revision, and task identifier.\n- Board, drawer, API, and CLI must agree on status, parent, branch, review URL, and merged timestamp.\n- If state reads are stale/unavailable, display an explicit indicator; never silently render obsolete state as authoritative.\n- Do not mutate task data to repair this display problem.\n\nTests:\n- Regression fixture where stale source/cache says Merged but state branch says Backlog; all views show Backlog.\n- Checkpoint update invalidates task list/detail caches without restart.\n- Verify per-project isolation and null merged_at cannot render Merged.\n- Verify degraded reads retain no false terminal status.\n\nAcceptance criteria:\n- Dashboard, detail pane, CLI/API, and canonical Markdown agree.\n- A task is Merged only when canonical state records it.\n- Operators can identify stale tracker data.\n- Relevant Makefile tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

