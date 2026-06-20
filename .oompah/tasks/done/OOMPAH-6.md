---
id: OOMPAH-6
type: bug
status: Done
priority: 2
title: Fix OVA GitHub issue intake authentication failure
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-06-20T02:13:20.696856Z'
updated_at: '2026-06-20T04:03:37.851788Z'
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
oompah.task_costs:
  total_input_tokens: 185
  total_output_tokens: 5650
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 185
      output_tokens: 5650
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 185
    output_tokens: 5650
    cost_usd: 0.0
    recorded_at: '2026-06-20T04:03:34.004304+00:00'
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
author: oompah
created: 2026-06-20 04:00
---
**Implementation:** Made the following changes to fix the OVA GitHub issue intake auth failure:

1. **tracker.py**: Added TrackerAuthError(TrackerError) subclass — a distinct exception class for non-retriable 401/403 credential failures vs generic tracker errors.

2. **github_tracker.py**: Changed request() and request_paginated() to raise TrackerAuthError (subclass of TrackerError, so backward-compatible) for HTTP 401 and 403 responses.

3. **github_intake_bridge.py**: In poll_github_issue_intake_project(), added specific except TrackerAuthError clause that: (a) logs a WARNING at the oompah logger with the project name, repo slug, and actionable advice to set project access_token; (b) re-raises the exception so callers can surface a dashboard alert.

4. **orchestrator.py**: In _sync_github_issue_intake_pass(), added except TrackerAuthError handler that surfaces a dashboard alert (level=error) with an actionable message. Also updated _error_class_for_tracker_exc() to classify TrackerAuthError as 'tracker_auth_failed' (distinct dedup key from 'tracker_failed').

5. **Tests**: Added 3 regression tests in test_github_intake_bridge.py covering: auth failure logs WARNING + re-raises TrackerAuthError, non-auth errors still return 0 silently. Added 5 tests in test_error_watcher_orchestrator.py for _error_class_for_tracker_exc().
---
author: oompah
created: 2026-06-20 04:02
---
**Verification:** All tests pass. 388 tests in the affected test files (test_github_intake_bridge.py, test_error_watcher_orchestrator.py, test_github_tracker.py) pass with no regressions. New tests added:
- test_poll_auth_failure_logs_warning_with_actionable_message: Confirms WARNING is logged with project name, repo slug, and access_token guidance
- test_poll_auth_failure_reraises_tracker_auth_error: Confirms TrackerAuthError propagates to orchestrator for alert surfacing
- test_poll_non_auth_error_still_returns_zero_and_does_not_reraise: Confirms non-auth errors remain silent/swallowed
- TestErrorClassForTrackerExc (5 cases): Confirms 'tracker_auth_failed' dedup class for TrackerAuthError vs 'tracker_failed' for generic TrackerError

Branch OOMPAH-6 pushed to origin.
---
author: oompah
created: 2026-06-20 04:03
---
**Completion:** Duplicate investigation confirmed no existing task covers this issue. Implementation delivered:

1. TrackerAuthError(TrackerError) subclass — distinct exception for 401/403 GitHub API failures, backward-compatible with all existing TrackerError catch sites.
2. github_tracker.py: request() and request_paginated() now raise TrackerAuthError for 401/403 so callers can distinguish auth failures from transient errors.
3. github_intake_bridge.py: poll_github_issue_intake_project() catches TrackerAuthError specifically, logs WARNING with actionable message (project name, repo slug, instructions for access_token / OOMPAH_GITHUB_TOKEN), re-raises for orchestrator alert surfacing.
4. orchestrator.py: _sync_github_issue_intake_pass() catches TrackerAuthError and surfaces a level=error dashboard alert with the project name and credential-fix instructions. _error_class_for_tracker_exc() classifies TrackerAuthError as 'tracker_auth_failed' (distinct dedup key).
5. 8 new regression tests covering all paths.

The OVA project auth failure is now surfaced as an actionable dashboard alert and WARNING log rather than silently dropped at DEBUG level. Operators are directed to set project access_token or configure OOMPAH_GITHUB_TOKEN with read access to NVIDIA-dev/ova.
---
author: oompah
created: 2026-06-20 04:03
---
Added TrackerAuthError subclass and surfaced GitHub intake auth failures as actionable dashboard alerts and WARNING logs. 8 regression tests added. No duplicate found.
---
author: oompah
created: 2026-06-20 04:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 125
- Tokens: 185 in / 5.7K out [5.8K total]
- Cost: $0.0000
- Exit: terminated, Duration: 26m 44s
- Log: OOMPAH-6__20260620T033658Z.jsonl
---
<!-- COMMENTS:END -->
