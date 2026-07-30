---
id: OOMPAH-629
type: bug
status: Backlog
priority: 1
title: Reject cross-task branch evidence before integration mutation
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T23:07:33.040594Z'
updated_at: '2026-07-30T23:07:55.854844Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: enforce the task-to-branch authority boundary before persisting submission metadata or leasing an integration row. The CLI and server submission path must reject a task identifier whose local/pushed task_branch does not equal the canonical issue work_branch (or another explicitly authorized canonical branch form), and the integration executor must never move the target task worktree or branch pointer when presented with foreign branch evidence. Preserve valid rebased task heads and normal explicit retry/rearm behavior. Relevant files include task CLI git-evidence construction, server submit validation, integration executor worktree preparation, and authority diagnostics. Reproducer: issuing 'oompah task submit OOMPAH-602' from the clean OOMPAH-593 worktree was accepted, wrote OOMPAH-593 branch/head into OOMPAH-602, then failed during integration after moving OOMPAH-602's local branch/HEAD to the foreign head; no foreign commit reached the epic. Tests: cover CLI wrong-worktree submission, direct API foreign branch evidence, pre-mutation rejection, unchanged tracker/queue/worktree/branch pointers after rejection, correct resubmission recovery, and same-head rearm compatibility. Acceptance criteria: cross-task evidence returns a safe 4xx before any durable or git mutation; executor defenses remain fail-closed; focused tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 23:07
---
Live corrupting-path reproducer was safely recovered before any foreign commit reached the epic. OOMPAH-602 is resubmitted from its canonical pushed branch; dispatch this child immediately as the final authority/race fix for OOMPAH-585.
---
<!-- COMMENTS:END -->
