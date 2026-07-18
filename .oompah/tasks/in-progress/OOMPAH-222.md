---
id: OOMPAH-222
type: bug
status: In Progress
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-32 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-32.md and
  /home/shedwards/.oompah/repos/trickle/.oo...'
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-18T01:07:12.334359Z'
updated_at: '2026-07-18T01:15:03.980019Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#427
  owner: lesserevil
  repo: oompah
  number: '427'
  url: https://github.com/lesserevil/oompah/issues/427
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Proposed
  last_synced_at: '2026-07-18T01:07:13.963563+00:00'
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
  last_validated_at: '2026-07-18T01:08:33.171527+00:00'
oompah.agent_run_id: 0647365b-5d50-4dd7-9210-27f8888c5c0a
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-32 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-32.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-32.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-32.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-32.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-32 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-32.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-32.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-32.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-32.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 41cbe445d6c2baf1
- dedup_fingerprint: 41cbe445d6c2baf1
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/427
- Requestor: @NVShawn
- Reference: lesserevil/oompah#427

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 01:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 01:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 01:11
---
Understanding: Investigating whether OOMPAH-222 (duplicate native oompah task ID error in backend:oompah_md_tracker) is a duplicate of an existing issue. The error occurs when a task file exists in two state directories simultaneously (in-progress/ and merged/), causing the tracker to emit a duplicate-ID warning captured by error_watcher. Will search existing tasks for prior reports of this same error pattern.
---
author: oompah
created: 2026-07-18 01:14
---
Discovery: Duplicate screening complete — OOMPAH-222 is NOT a duplicate.

**Closest related task reviewed:** OOMPAH-212 (Merged, 2026-07-16) — 'Prevent duplicate native task records from appearing on the board'
- OOMPAH-212 added the winner/loser deduplication logic in oompah/oompah_md_tracker.py (around line 862-879), selecting the most-recently-updated file when a task appears in two state directories simultaneously.
- OOMPAH-212 is NOT the same issue: it fixed the board display (prevents duplicates from appearing as separate entries). It did NOT prevent the error from being reported to error_watcher.

**Root cause of OOMPAH-222:** The deduplication code (oompah/oompah_md_tracker.py:872) uses logger.error() when a duplicate ID is detected. Error_watcher picks up logger.error() messages and auto-files them as bugs. The fix in OOMPAH-212 made the tracker handle duplicates gracefully but still emits an error-level log, triggering error_watcher.

**Scale of the problem:** 13 instances total filed on 2026-07-18 — OOMPAH-220 (TRICKLE-30), OOMPAH-221 (TRICKLE-31), OOMPAH-222 (TRICKLE-32), OOMPAH-223 through OOMPAH-232 (TRICKLE-36 through TRICKLE-45) — all describe the identical root cause.

**Evidence files:** oompah/oompah_md_tracker.py line 872 (logger.error call in the duplicate-resolution block)
---
<!-- COMMENTS:END -->
