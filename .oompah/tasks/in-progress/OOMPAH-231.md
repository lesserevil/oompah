---
id: OOMPAH-231
type: bug
status: In Progress
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-44 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-44.md and
  /home/shedwards/.oompah/repos/trickle/.oo...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-18T01:07:55.118753Z'
updated_at: '2026-07-18T01:47:29.519977Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#436
  owner: lesserevil
  repo: oompah
  number: '436'
  url: https://github.com/lesserevil/oompah/issues/436
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Open
  last_synced_at: '2026-07-18T01:47:28.817818+00:00'
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
  last_validated_at: '2026-07-18T01:09:52.990425+00:00'
oompah.agent_run_id: 85acb1ec-2307-406c-9017-f5a4c92fd698
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-44 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-44.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-44.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-44.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-44.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-44 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-44.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-44.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-44.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-44.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 8d7cd7bfad9137f9
- dedup_fingerprint: 8d7cd7bfad9137f9
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/436
- Requestor: @NVShawn
- Reference: lesserevil/oompah#436

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 01:47
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 01:47
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
