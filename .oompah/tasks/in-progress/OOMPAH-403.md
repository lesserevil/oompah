---
id: OOMPAH-403
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Worker did not stop within 10000ms; continuing shutdown
  issue_identifier=OOMPAH-339'
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-22T05:35:11.758325Z'
updated_at: '2026-07-22T05:42:33.026489Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#531
  owner: lesserevil
  repo: oompah
  number: '531'
  url: https://github.com/lesserevil/oompah/issues/531
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-22T05:40:53.616145+00:00'
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
  last_validated_at: '2026-07-22T05:35:18.775008+00:00'
oompah.agent_run_id: 3a7b4c04-d8d9-4f8b-a9c3-7d0daeaf5c21
---
## Summary

### Problem

Oompah detected a backend error from `backend:orchestrator`:

> Worker did not stop within 10000ms; continuing shutdown issue_identifier=OOMPAH-339

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Worker did not stop within 10000ms; continuing shutdown issue_identifier=OOMPAH-339

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 93c60c1dea846b57
- dedup_fingerprint: 93c60c1dea846b57
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/531
- Requestor: @NVShawn
- Reference: lesserevil/oompah#531

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:35
---
Understanding: This issue is an auto-filed error report from the error_watcher. The error 'Worker did not stop within 10000ms; continuing shutdown' occurred in backend:orchestrator while processing OOMPAH-339. My role is Duplicate Investigator — I need to determine if this shutdown timeout issue is already tracked in an existing task. Plan: (1) Search .oompah/tasks for 'worker', 'shutdown', 'timeout', and 'stop within' keywords; (2) View OOMPAH-339 for context; (3) Check for any existing tasks covering the same shutdown timeout problem.
---
author: oompah
created: 2026-07-22 05:42
---
Discovery: OOMPAH-403 is NOT a duplicate. Duplicate screening complete.

**Root cause identified:**
The error originates in oompah/orchestrator.py line 18906 where logger.error() logs 'Worker did not stop within Xms; continuing shutdown issue_identifier=OOMPAH-339'. This is logged when the orchestrator cancels a running worker task for OOMPAH-339 during shutdown and the worker doesn't complete cancellation within worker_termination_timeout_ms (10000ms default). The logger.error() call is what triggers error_watcher to auto-file this task.

Looking at OOMPAH-339's comment history, there were multiple 'terminated' exit events (comments #57 and #64) where workers were killed mid-run, which is the scenario that triggers this code path.

**Search scope:**
- All .oompah/tasks/ states: archived (225+), merged (53+), done (1), open (1), backlog (1)
- Searched: 'stop within', '10000ms', 'did not stop', 'Worker did not stop', 'backend:orchestrator', 'shutdown.*worker', 'worker.*shutdown'
- All returned zero results

**Closest candidates reviewed (NOT duplicates):**
- OOMPAH-339 (In Progress): This is the SUBJECT of the error (the worker that wouldn't stop), not a duplicate. OOMPAH-339 is about GitLab status-label governance — a completely different concern.
- OOMPAH-282 (Backlog): Different auto-filed error (UnicodeEncodeError in state_branch_migration), same error_watcher mechanism but different root cause.
- OOMPAH-118/188/113/161: Other auto-filed errors from backend:webhooks and backend:server — different backends and different error conditions.

**Root cause options for the implementation agent:**
1. Downgrade logger.error() → logger.warning() at orchestrator.py:18906 so error_watcher doesn't file tasks for expected shutdown timeouts
2. Increase worker_termination_timeout_ms (configurable via .env) to give long-running agent processes more time to exit cleanly
3. Filter this specific error class in error_watcher to suppress known-acceptable shutdown noise

Key file: oompah/orchestrator.py ~line 18890-18930 (the _cancel_running_worker or similar method)
---
<!-- COMMENTS:END -->
