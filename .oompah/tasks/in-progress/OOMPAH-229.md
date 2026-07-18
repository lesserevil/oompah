---
id: OOMPAH-229
type: bug
status: In Progress
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-42 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-42.md and /home/shedwards/.oompah/repos/trickle/.oompah/ta...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-18T01:07:46.132574Z'
updated_at: '2026-07-18T02:08:41.296550Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#434
  owner: lesserevil
  repo: oompah
  number: '434'
  url: https://github.com/lesserevil/oompah/issues/434
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Open
  last_synced_at: '2026-07-18T01:47:23.144049+00:00'
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
  last_validated_at: '2026-07-18T01:09:25.652241+00:00'
oompah.agent_run_id: 216c8f38-bde8-4c1f-a513-b8e4825b46a7
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-42 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-42.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-42.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-42.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-42.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-42 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-42.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-42.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-42.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-42.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 8de9177c891b1e5a
- dedup_fingerprint: 8de9177c891b1e5a
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/434
- Requestor: @NVShawn
- Reference: lesserevil/oompah#434

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 02:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 02:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 02:07
---
Understanding: Investigating OOMPAH-229 as Duplicate Investigator. This bug reports that oompah_md_tracker emits an error when the same task ID (TRICKLE-42) exists in two subdirectories (done/ and merged/). The error_watcher then auto-files this as a task. I will search for prior tasks covering the same duplicate-ID detection issue in oompah_md_tracker before deciding if this is a new issue or a duplicate.
---
author: oompah
created: 2026-07-18 02:08
---
Discovery: OOMPAH-229 is a confirmed duplicate of OOMPAH-220.

OOMPAH-220 is the canonical task for this exact bug: `oompah/oompah_md_tracker.py:871` used `logger.error()` in the duplicate-ID resolution block (`_read_records()`). The code already handled duplicates gracefully (picks most-recently-updated file, continues), but the ERROR log level caused `error_watcher` to auto-file a bug for every occurrence.

**Fix already applied in OOMPAH-220:** `logger.error()` → `logger.warning()` (commit 625014c3, PR #438, now merged). Current code at line 871 confirms `logger.warning`.

**OOMPAH-220's duplicate_detector** explicitly named OOMPAH-229 (trickle-42) as one of 12 sibling tasks filed in the same error_watcher burst. All siblings were filed at the same time as a result of the same stale trickle repo files being detected on the same scan.

Archiving OOMPAH-229 as duplicate-of:OOMPAH-220.
---
<!-- COMMENTS:END -->
