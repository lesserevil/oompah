---
id: OOMPAH-360
type: bug
status: Proposed
priority: 2
title: '[backend:orchestrator] Worker did not stop within 10000ms; continuing shutdown
  issue_identifier=OOMPAH-357'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-22T01:30:09.469717Z'
updated_at: '2026-07-22T01:30:14.685778Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#490
  owner: lesserevil
  repo: oompah
  number: '490'
  url: https://github.com/lesserevil/oompah/issues/490
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Proposed
  last_synced_at: '2026-07-22T01:30:09.624705+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:orchestrator`:

> Worker did not stop within 10000ms; continuing shutdown issue_identifier=OOMPAH-357

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Worker did not stop within 10000ms; continuing shutdown issue_identifier=OOMPAH-357

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: f37f0bf0f463d042
- dedup_fingerprint: f37f0bf0f463d042
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/490
- Requestor: @NVShawn
- Reference: lesserevil/oompah#490

## Notes


