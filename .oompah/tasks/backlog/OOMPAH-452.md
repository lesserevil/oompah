---
id: OOMPAH-452
type: bug
status: Backlog
priority: 1
title: Recover the GitLab Issues tracker implementation onto main
parent: OOMPAH-451
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T12:34:50.818103Z'
updated_at: '2026-07-28T12:34:50.818103Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem: OOMPAH-337 through OOMPAH-339 are marked Merged, but current main has no oompah/gitlab_tracker.py and no reachable GitLab Issues tracker registration. Their implementation survives only on origin/epic-OOMPAH-318 after the parent epic merged early.

Implementation scope: selectively reconcile the GitLabIssueTracker adapter, protocol registration, metadata persistence, pagination, relationships, comments, labels, status governance, authorized-actor audit and revert behavior from the stranded commits onto current tracker interfaces. Preserve current GitHub and native Markdown behavior. Relevant files include oompah/gitlab_tracker.py, oompah/tracker.py, oompah/server.py, and tests/test_gitlab_tracker.py.

Tests: restore and update the GitLab tracker contract/lifecycle tests, status authorization tests, pagination and API failure fixtures, plus existing tracker protocol tests; run make test.

Acceptance criteria: tracker_kind=gitlab_issues resolves to a complete TrackerProtocol implementation on main; task and epic lifecycle operations round-trip through GitLab Issues; secrets remain redacted; GitHub and native tracker regressions remain green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

