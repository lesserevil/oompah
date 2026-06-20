---
id: OOMPAH-6
type: bug
status: Proposed
priority: 2
title: Fix OVA GitHub issue intake authentication failure
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-06-20T02:13:20.696856Z'
updated_at: '2026-06-20T03:27:25.869885Z'
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
  last_synced_status: Proposed
  last_synced_at: '2026-06-20T02:13:20.699732Z'
  migrated_at: '2026-06-20T02:13:20.699738Z'
  migrated_from_tracker: github_issues
  external_state: open
  external_created_at: '2026-06-20T01:59:20Z'
  external_updated_at: '2026-06-20T02:13:50Z'
oompah.intake:
  missing_fields:
  - acceptance_criteria
  - reproduction_steps
  scope: small
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: fail
  last_validated_at: '2026-06-20T03:27:24.594446+00:00'
---
## Summary

OVA GitHub issue intake is failing because oompah cannot authenticate when fetching issues from https://api.github.com/repos/NVIDIA-dev/ova/issues. Actual behavior: the fetch records a tracker_failed error and prevents OVA issue reconciliation. Expected behavior: oompah should authenticate successfully or show an actionable credential error. Reproduction steps and acceptance criteria are documented below.
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
