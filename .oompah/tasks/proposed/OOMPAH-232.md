---
id: OOMPAH-232
type: bug
status: Proposed
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-45 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-45.md and /home/shedwards/.oompah/repos/trickle/.oompah/...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-18T01:08:04.577980Z'
updated_at: '2026-07-18T01:08:04.577980Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-45 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-45.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/needs-human/TRICKLE-45.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-45.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/needs-human/TRICKLE-45.md. Repair the stale record before editing this task.

### Steps to Reproduce
1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-45 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-45.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/needs-human/TRICKLE-45.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-45.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/needs-human/TRICKLE-45.md. Repair the stale record before editing this task.

### Expected Behavior
The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: c5878159cd5184dd
- dedup_fingerprint: c5878159cd5184dd
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/437
- Requestor: @NVShawn
- Reference: lesserevil/oompah#437

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

