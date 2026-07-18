---
id: OOMPAH-230
type: bug
status: Archived
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-43 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-43.md and /home/shedwards/.oompah/repos/trickle/.oompah/ta...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-18T01:07:50.707111Z'
updated_at: '2026-07-18T02:10:52.011960Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#435
  owner: lesserevil
  repo: oompah
  number: '435'
  url: https://github.com/lesserevil/oompah/issues/435
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Open
  last_synced_at: '2026-07-18T01:47:25.967987+00:00'
oompah.intake:
  missing_fields: []
  scope: unknown
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: pass
  last_validated_at: '2026-07-18T01:09:39.548177+00:00'
oompah.agent_run_id: a65fa073-89b0-4338-9452-74f85f5ccc21
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-43 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-43.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-43.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-43.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-43.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-43 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-43.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-43.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-43.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-43.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 45855d248ba99014
- dedup_fingerprint: 45855d248ba99014
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/435
- Requestor: @NVShawn
- Reference: lesserevil/oompah#435

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 02:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 02:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 02:09
---
Understanding: I am a Duplicate Investigator for this bug. The error is about a duplicate native oompah task ID (trickle-43) appearing in both the 'done' and 'merged' directories of the oompah_md_tracker. My plan: (1) search for similar tasks about duplicate task IDs or oompah_md_tracker errors, (2) review any candidate duplicates in full, (3) archive if confirmed duplicate or hand off to implementation if unique.
---
author: oompah
created: 2026-07-18 02:10
---
Discovery: OOMPAH-230 is a confirmed duplicate of OOMPAH-220.

OOMPAH-220 is the canonical task for this exact bug class. The root cause was `oompah/oompah_md_tracker.py:871` using `logger.error()` in the duplicate-ID resolution block (`_read_records()`). The code already handled duplicates gracefully (picks the most-recently-updated file and continues), but the ERROR log level caused `error_watcher` to auto-file a bug for every occurrence.

**Fix already applied in OOMPAH-220:** `logger.error()` → `logger.warning()` (commit 625014c3, PR #438, merged). A regression test was also added: `test_duplicate_task_id_logs_warning_not_error` in `tests/test_oompah_md_tracker.py`.

OOMPAH-220's duplicate_detector explicitly identified OOMPAH-230 (trickle-43) as one of the sibling tasks in the same error_watcher burst. All siblings (OOMPAH-221 through OOMPAH-232) were filed at the same time from the same stale trickle repo files being detected in the same scan.

Archiving as duplicate-of:OOMPAH-220.
---
author: oompah
created: 2026-07-18 02:10
---
duplicate-of:OOMPAH-220
---
<!-- COMMENTS:END -->
