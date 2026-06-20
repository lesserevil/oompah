---
id: OOMPAH-6
type: bug
status: In Progress
priority: 2
title: Fix OVA GitHub issue intake authentication failure
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-06-20T02:13:20.696856Z'
updated_at: '2026-06-20T03:49:08.711835Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#334
  owner: lesserevil
  repo: oompah
  number: '334'
  url: https://github.com/lesserevil/oompah/issues/334
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-06-20T03:39:18.062765+00:00'
  migrated_at: '2026-06-20T02:13:20.699738Z'
  migrated_from_tracker: github_issues
  external_state: open
  external_created_at: '2026-06-20T01:59:20Z'
  external_updated_at: '2026-06-20T02:13:50Z'
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
  last_validated_at: '2026-06-20T03:28:26.847556+00:00'
oompah.agent_run_id: 348fee7f-4bde-4602-84f3-a0042536c2af
---
## Summary

### Problem
Oompah cannot fetch GitHub issues for the managed OVA project during GitHub issue intake. The tracker fetch fails against `https://api.github.com/repos/NVIDIA-dev/ova/issues`, which prevents oompah from reconciling external GitHub issues into native oompah tasks for that project.

### Steps to Reproduce
1. Run the oompah service with the OVA managed project configured for GitHub issue intake.
2. Let the GitHub issue intake poller or webhook reconciliation fetch issues for `NVIDIA-dev/ova`.
3. Observe the tracker failure recorded by the error watcher: `GitHub API authentication failed fetching page https://api.github.com/repos/NVIDIA-dev/ova/issues`.

### Actual Behavior
The fetch fails with a GitHub API authentication error. Oompah records a `tracker_failed` error for the OVA project and cannot reliably import or reconcile OVA GitHub issues while the credential problem persists.

### Expected Behavior
Oompah should authenticate successfully when fetching `NVIDIA-dev/ova` issues, or it should surface a clear actionable configuration error identifying the token or GitHub App credentials that need to be fixed. The OVA GitHub issue intake path should resume once valid credentials are configured.

### Environment
Managed project: OVA (`NVIDIA-dev/ova`). Tracker: `github_issues:lesserevil/oompah`. Failure surfaced by the oompah `error_watcher` while reconciling GitHub issue intake.

### Acceptance Criteria
- The OVA project can fetch `https://api.github.com/repos/NVIDIA-dev/ova/issues` without a GitHub API authentication failure.
- Oompah surfaces an actionable project alert if the configured token or GitHub App installation cannot access the OVA issues API.
- A regression test or documented verification covers the failed-auth path and confirms the generated error task remains validator-ready.
- The fix preserves the diagnostic metadata below for future deduplication and troubleshooting.

### Diagnostic Metadata
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 4dba66ecb4abddff
- dedup_fingerprint: 4dba66ecb4abddff
- tracker_owner: lesserevil
- tracker_repo: oompah
- error_class: tracker_failed
- triggering_message: Fetch failed for project ova: GitHub API authentication failed fetching page https://api.github.com/repos/NVIDIA-dev/ova/issues. Check OOMPAH_GITHUB_TOKEN or GitHub App credentials.
## Problem
Oompah cannot fetch GitHub issues for the managed OVA project during GitHub issue intake. The tracker fetch fails against `https://api.github.com/repos/NVIDIA-dev/ova/issues`, which prevents oompah from reconciling external GitHub issues into native oompah tasks for that project.

## Steps to Reproduce
1. Run the oompah service with the OVA managed project configured for GitHub issue intake.
2. Let the GitHub issue intake poller or webhook reconciliation fetch issues for `NVIDIA-dev/ova`.
3. Observe the tracker failure recorded by the error watcher: `GitHub API authentication failed fetching page https://api.github.com/repos/NVIDIA-dev/ova/issues`.

## Actual Behavior
The fetch fails with a GitHub API authentication error. Oompah records a `tracker_failed` error for the OVA project and cannot reliably import or reconcile OVA GitHub issues while the credential problem persists.

## Expected Behavior
Oompah should authenticate successfully when fetching `NVIDIA-dev/ova` issues, or it should surface a clear actionable configuration error identifying the token or GitHub App credentials that need to be fixed. The OVA GitHub issue intake path should resume once valid credentials are configured.

## Environment
Managed project: OVA (`NVIDIA-dev/ova`). Tracker: `github_issues:lesserevil/oompah`. Failure surfaced by the oompah `error_watcher` while reconciling GitHub issue intake.

## Acceptance Criteria
- The OVA project can fetch `https://api.github.com/repos/NVIDIA-dev/ova/issues` without a GitHub API authentication failure.
- Oompah surfaces an actionable project alert if the configured token or GitHub App installation cannot access the OVA issues API.
- A regression test or documented verification covers the failed-auth path and confirms the generated error task remains validator-ready.
- The fix preserves the diagnostic metadata below for future deduplication and troubleshooting.

## Diagnostic Metadata
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 4dba66ecb4abddff
- dedup_fingerprint: 4dba66ecb4abddff
- tracker_owner: lesserevil
- tracker_repo: oompah
- error_class: tracker_failed
- triggering_message: Fetch failed for project ova: GitHub API authentication failed fetching page https://api.github.com/repos/NVIDIA-dev/ova/issues. Check OOMPAH_GITHUB_TOKEN or GitHub App credentials.
## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/334
- Requestor: @lesserevil
- Reference: lesserevil/oompah#334

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-20 03:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-20 03:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-20 03:37
---
**Understanding:** Investigating OOMPAH-6 as Duplicate Investigator. The issue reports that oompah fails to fetch GitHub issues for the OVA project (NVIDIA-dev/ova) with a GitHub API authentication failure. Before implementing any fix, I need to search for existing tasks covering the same authentication failure or OVA project issues to determine if this is a duplicate. Plan: (1) search .oompah/tasks and docs for similar auth/OVA failures, (2) read candidate duplicates in full, (3) archive if duplicate or proceed with implementation if new.
---
author: oompah
created: 2026-06-20 03:49
---
**Discovery:** No duplicate found. This is a unique issue. Searched all .oompah/tasks (OOMPAH-1 through OOMPAH-15) - OOMPAH-15 covers auto-generated task format validation but NOT the underlying auth failure. OOMPAH-6 is specifically about the GitHub API authentication failure when fetching NVIDIA-dev/ova issues.

Root cause: The OVA project (proj-edbc8b4c) uses oompah_md tracker with github_issue_intake_enabled=true. The _github_tracker_for_project() function in github_intake_bridge.py builds a GitHubIssueTracker for NVIDIA-dev/ova. When no project-level access_token is set, it falls back to global GitHubAuth() (OOMPAH_GITHUB_TOKEN) which doesn't have access to NVIDIA-dev/ova. The resulting 401 auth error is caught and logged at DEBUG level only - never surfaced as a warning or alert.

Implementation plan:
1. Add TrackerAuthError(TrackerError) subclass to tracker.py for distinguishing auth failures
2. Raise TrackerAuthError for 401 in request_paginated() in github_tracker.py
3. In poll_github_issue_intake_project(): catch TrackerAuthError separately, log at WARNING with actionable message about setting project access_token
4. In orchestrator._sync_github_issue_intake_pass(): surface dashboard alert for auth failures
5. Add regression tests for the auth failure path
---
<!-- COMMENTS:END -->
