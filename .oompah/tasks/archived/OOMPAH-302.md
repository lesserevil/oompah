---
id: OOMPAH-302
type: bug
status: Archived
priority: 2
title: '[backend:server] Fetch issues failed for project exocomp: State branch ''oompah/state/proj-c260b117''
  does not exist locally or at origin/''oompah/state/proj-c260b117''. Run the bootstrap
  or migration ...'
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T15:27:26.037712Z'
updated_at: '2026-07-21T15:49:27.066368Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#465
  owner: lesserevil
  repo: oompah
  number: '465'
  url: https://github.com/lesserevil/oompah/issues/465
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: Backlog
  last_synced_at: '2026-07-21T15:37:23.669219+00:00'
oompah.intake:
  missing_fields: []
  scope: small
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: pass
  last_validated_at: '2026-07-21T15:27:32.006759+00:00'
oompah.agent_run_id: ab444e63-c347-4463-97be-3db65a5c9917
---
## Summary

### Problem

Oompah detected a backend error from `backend:server`:

> Fetch issues failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Desired Behavior

The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Fetch issues failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Acceptance Criteria

- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 9a803f3b8b56abc0
- dedup_fingerprint: 9a803f3b8b56abc0
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/465
- Requestor: @lesserevil
- Reference: lesserevil/oompah#465

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 15:46
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 15:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 15:49
---
Understanding: Investigating OOMPAH-302 as Duplicate Investigator. The error is 'Fetch issues failed for project exocomp: State branch oompah/state/proj-c260b117 does not exist locally or at origin/...' which originates from oompah/oompah_md_tracker.py:1310 (TrackerError raised in _get_state_root() when state_branch_enabled=True but the branch doesn't exist) and is logged at error level in oompah/server.py:2569, triggering error_watcher. Plan: search all tasks for state_branch, Fetch issues failed, proj-c260b117, exocomp, and bootstrap/migration patterns to identify any prior task covering this.
---
author: oompah
created: 2026-07-21 15:49
---
Discovery: Duplicate screening complete. No duplicate found.

**Evidence searched:**
- All .oompah/tasks/ states (archived/223, backlog/1, done/1, merged, needs-ci-fix, needs-rebase) — 230+ tasks scanned
- rg patterns: state.branch, state_branch, Fetch issues failed, proj-c260b117, exocomp, bootstrap.*migration, does not exist locally or at origin, Normal tracker reads must not create remote branches

**Closest candidates reviewed and ruled out:**

1. **OOMPAH-282** (Backlog) — State branch migration error for proj-edbc8b4c. Different project, different error (UnicodeEncodeError in initialize_state_branch() during Stage A migration). NOT the same issue.

2. **OOMPAH-256** (Merged) — Implemented the OompahMarkdownTracker state-branch feature including _get_state_root() raising TrackerError when branch is missing. This is the code that triggers the error in OOMPAH-302, but OOMPAH-256 is a feature task, not a bug report about the error surfacing via error_watcher.

**Root cause identified:** Project exocomp (proj-c260b117) exists as a managed project with tracker_kind=oompah_md. When fetch_issues is called, if state_branch_enabled=True for this project but the branch oompah/state/proj-c260b117 was never bootstrapped, _get_state_root() raises TrackerError which is logged at error level in server.py:2569, triggering error_watcher.

**No existing task covers:** graceful handling of this TrackerError so it does not trigger error_watcher, OR running bootstrap for exocomp's state branch.

Recommended next focus: bug fix — either (a) lower the log level for this specific TrackerError case (warning not error) in server.py, or (b) auto-bootstrap the state branch when missing, or (c) run the bootstrap/migration for proj-c260b117 directly. Option (a) is the safest without data loss risk.
---
<!-- COMMENTS:END -->
