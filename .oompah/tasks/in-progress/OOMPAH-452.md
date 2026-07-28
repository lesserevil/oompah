---
id: OOMPAH-452
type: bug
status: In Progress
priority: 1
title: Recover the GitLab Issues tracker implementation onto main
parent: OOMPAH-451
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T12:34:50.818103Z'
updated_at: '2026-07-28T12:42:00.056838Z'
work_branch: epic-OOMPAH-451
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 64d2bfaf-3c22-48d0-96ac-4134e49cfc20
oompah.work_branch: epic-OOMPAH-451
---
## Summary

Problem: OOMPAH-337 through OOMPAH-339 are marked Merged, but current main has no oompah/gitlab_tracker.py and no reachable GitLab Issues tracker registration. Their implementation survives only on origin/epic-OOMPAH-318 after the parent epic merged early.

Implementation scope: selectively reconcile the GitLabIssueTracker adapter, protocol registration, metadata persistence, pagination, relationships, comments, labels, status governance, authorized-actor audit and revert behavior from the stranded commits onto current tracker interfaces. Preserve current GitHub and native Markdown behavior. Relevant files include oompah/gitlab_tracker.py, oompah/tracker.py, oompah/server.py, and tests/test_gitlab_tracker.py.

Tests: restore and update the GitLab tracker contract/lifecycle tests, status authorization tests, pagination and API failure fixtures, plus existing tracker protocol tests; run make test.

Acceptance criteria: tracker_kind=gitlab_issues resolves to a complete TrackerProtocol implementation on main; task and epic lifecycle operations round-trip through GitLab Issues; secrets remain redacted; GitHub and native tracker regressions remain green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 12:41
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 12:42
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
