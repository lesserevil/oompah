---
id: OOMPAH-266
type: task
status: Archived
priority: null
title: Do not auto-file epic rebase tasks for tracker-only main divergence
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-20T16:49:00.743485Z'
updated_at: '2026-07-20T16:52:04.642459Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem

The epic stale-branch monitor files tasks such as OOMPAH-261 and OOMPAH-262 to rebase epic-OOMPAH-253 onto main while the epic is still being worked. The current trigger treats any main advancement as stale, including commits that only update .oompah task metadata. OOMPAH-261 confirmed 49 commits behind with no unique epic work and required only a trivial fast-forward. This produces unnecessary agents and rebases.

Required implementation

- Update epic stale-branch detection to distinguish meaningful code, documentation, configuration, and workflow divergence from tracker-only .oompah changes.
- Do not auto-file, dispatch, or retain an epic rebase task when the only commits the epic branch lacks are tracker-only changes.
- Preserve the existing rebase workflow when main contains relevant non-tracker changes.
- Re-evaluate an existing open or in-progress auto-generated rebase task before dispatch; close or archive it with an explanatory comment if its divergence is tracker-only.
- Remain compatible with OOMPAH-253 state-branch migration, which will remove routine tracker commits from main entirely.

Tests

- Git fixture: an epic branch behind main only by .oompah task commits does not create a rebase task.
- Counterexample: a branch behind by a source or documentation commit still creates a rebase task.
- Existing queued rebase task is suppressed when a fresh divergence check proves it is tracker-only.
- Verify nested shared epic behavior is unchanged.

Acceptance criteria

- Routine Oompah task updates no longer create rebase-to-main work for a still-active epic.
- Real code divergence still receives the existing rebase protection.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 16:50
---
Archived by project owner direction: the tracker-only rebase tasks are harmless extra work, and OOMPAH-253 will remove the underlying main-branch metadata churn. Do not implement a separate interim suppression change.
---
author: oompah
created: 2026-07-20 16:51
---
Archived by project owner direction: the tracker-only rebase tasks are harmless extra work, and OOMPAH-253 will remove the underlying main-branch metadata churn. Do not implement a separate interim suppression change.
---
author: oompah
created: 2026-07-20 16:51
---
Archived by project owner direction: the tracker-only rebase tasks are harmless extra work, and OOMPAH-253 will remove the underlying main-branch metadata churn. Do not implement a separate interim suppression change.
---
author: oompah
created: 2026-07-20 16:52
---
Superseded by the state-branch epic OOMPAH-253; no separate fix needed.
---
<!-- COMMENTS:END -->
