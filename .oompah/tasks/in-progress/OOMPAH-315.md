---
id: OOMPAH-315
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Fetch failed for project exocomp: State branch ''oompah/state/proj-c260b117''
  does not exist locally or at origin/''oompah/state/proj-c260b117''. Run the bootstrap
  or migration f...'
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T18:20:09.334393Z'
updated_at: '2026-07-21T18:49:35.587496Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#470
  owner: lesserevil
  repo: oompah
  number: '470'
  url: https://github.com/lesserevil/oompah/issues/470
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: Backlog
  last_synced_at: '2026-07-21T18:30:10.844005+00:00'
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
  last_validated_at: '2026-07-21T18:20:20.176791+00:00'
oompah.agent_run_id: 04eb409e-6918-42da-876d-f4b5bb31895a
---
## Summary

### Problem

Oompah detected a backend error (error class: `tracker_failed`) from `backend:orchestrator`:

> Fetch failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Fetch failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 4dba66ecb4abddff
- dedup_fingerprint: 4dba66ecb4abddff
- tracker_owner: lesserevil
- tracker_repo: oompah
- error_class: tracker_failed

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/470
- Requestor: @lesserevil
- Reference: lesserevil/oompah#470

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 18:44
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 18:44
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 18:45
---
Understanding: Investigating OOMPAH-315 as Duplicate Investigator. The error is about project 'exocomp' (proj-c260b117) having state_branch_enabled=True but the state branch 'oompah/state/proj-c260b117' doesn't exist locally or at origin. This triggers a tracker_failed error caught by error_watcher. My plan: search for similar existing tasks about state branch missing errors, state_branch_enabled misconfiguration, or the same proj-c260b117 project to determine if this is a duplicate.
---
author: oompah
created: 2026-07-21 18:49
---
Discovery: Duplicate screening complete. OOMPAH-315 is NOT a duplicate.

Key findings:
1. **Same fingerprint as OOMPAH-6 (archived)** — both have dedup_fingerprint 4dba66ecb4abddff, but this is because ALL tracker_failed errors share one fingerprint (computed as sha256('class=tracker_failed')[:16] in error_watcher.py). OOMPAH-6 was about a GitHub API auth failure for the OVA project; that's a completely different root cause. Not a duplicate.
2. **OOMPAH-282 (backlog)** — closest in topic (state branch migration failure), but covers proj-edbc8b4c with a UnicodeEncodeError during Stage A migration. Different project, different error. Not a duplicate.
3. **OOMPAH-253 epic + children (OOMPAH-254 through OOMPAH-260, all merged)** — implemented the state branch feature. OOMPAH-256 specifically added the intentional TrackerError when the state branch doesn't exist ('Normal reads must not auto-create the state branch'). But none of these tasks addressed what should happen when error_watcher picks up this expected configuration error and auto-files it.

Root cause identified: Project exocomp (proj-c260b117) is in the system with state_branch_enabled=True, but its state branch 'oompah/state/proj-c260b117' does not exist locally or at origin. The TrackerError raised in oompah_md_tracker.py:1312 propagates through the orchestrator as tracker_failed, triggering error_watcher to auto-file this task repeatedly.

Relevant files:
- oompah/oompah_md_tracker.py:1280-1315 (where the TrackerError is raised)
- oompah/orchestrator.py:151-173 (_error_class_for_tracker_exc — classifies as tracker_failed)
- oompah/error_watcher.py:508-540 (fingerprinting — all tracker_failed share same hash)
- oompah/server.py:10662 (state_branch_enabled=True set during migration Stage A)

The fix options are: (a) run the bootstrap/migration for exocomp to create its state branch, OR (b) add a distinct error class for 'missing state branch' to prevent error_watcher from auto-filing it, OR (c) suppress the error in the orchestrator when it's a known configuration state. A devops or backend agent should assess which is appropriate.
---
<!-- COMMENTS:END -->
