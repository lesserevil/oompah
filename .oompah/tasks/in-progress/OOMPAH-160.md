---
id: OOMPAH-160
type: bug
status: In Progress
priority: null
title: Make native task writes atomic and block intake reimports for corrupt tasks
parent: null
children: []
blocked_by: []
labels:
- needs:backend
assignee: null
created_at: '2026-06-29T14:46:06.483875Z'
updated_at: '2026-06-29T15:26:53.409972Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 1d4e0ec5-5030-4d8e-b215-e7a29381999d
---
## Summary

Triggered by: TRICKLE-8

### Summary
Native oompah Markdown task writes should be atomic and GitHub intake should not recreate an already-imported issue just because the existing native task file is corrupt or unreadable.

### Problem
TRICKLE-8 was in progress on 2026-06-29 when the host had disk-full errors. The tracked file `.oompah/tasks/in-progress/TRICKLE-8.md` became a zero-byte file, causing the native tracker to skip it with `Missing YAML front matter`. Because the valid task was no longer visible to intake lookup, GitHub issue intake treated NVIDIA-Omniverse/trickle#268 as not imported and created a fresh Proposed `TRICKLE-8`, which then validated back to Backlog.

This caused an active task to disappear from the scheduler, terminate its running agent, and re-enter the intake flow as if it were new.

### Evidence
- `oompah.log` shows repeated warnings starting at 2026-06-29T14:23:40Z: `Skipping invalid native oompah task ... .oompah/tasks/in-progress/TRICKLE-8.md: Missing YAML front matter`.
- The current tracked `.oompah/tasks/in-progress/TRICKLE-8.md` in the trickle managed repo is zero bytes.
- Commit `822e8423` in the trickle managed repo both emptied the old in-progress TRICKLE-8 file and created a new `.oompah/tasks/proposed/TRICKLE-8.md`.
- Commit `0f1a5540` then moved the recreated task from Proposed to Backlog after validation passed.
- `oompah/oompah_md_tracker.py` currently writes task files with `path.write_text(...)`, which truncates the destination before the full replacement content is durable.

### Expected Behavior
A failed write must not corrupt or empty an existing task file. If a task file is corrupt or unreadable, GitHub intake should treat that as a repair/blocking condition for the existing task identity or external issue reference, not create a duplicate replacement task with the same identifier.

### Acceptance Criteria
- Native Markdown task writes use atomic replacement: write to a temporary file in the same directory, fsync where practical, then rename/replace the original only after the full payload is written.
- A regression test simulates a write failure and verifies the previous task file remains intact.
- GitHub intake duplicate detection/import lookup detects corrupt/unreadable native task files that match an existing task id or external GitHub issue metadata when possible, and does not create a duplicate task.
- When a corrupt native task file is found, oompah surfaces an actionable alert or moves the task to a repair flow instead of silently skipping it.
- Existing invalid zero-byte task files do not poison candidate selection or cause repeated intake reimports.
- Regression coverage includes the TRICKLE-8 failure mode: an in-progress task file becomes zero bytes, GitHub issue intake polls the same external issue, and no new Proposed task is created.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-29 15:26
---
Agent dispatched (profile: deep)
---
<!-- COMMENTS:END -->
