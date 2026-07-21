---
id: OOMPAH-323
type: task
status: Backlog
priority: 1
title: Implement GitLab Issues tracker with Oompah status governance
parent: OOMPAH-318
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T20:34:25.248230Z'
updated_at: '2026-07-21T20:34:25.248230Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, GitLab implementation.

Add GitLabIssueTracker implementing every TrackerProtocol operation through GitLab Issues, notes, labels, and issue links. Use oompah:status:* labels for canonical state, preserve priority/type/parent/dependency behavior, enforce authorized status-label actors, audit/revert unauthorized transitions, and support comments, attachments metadata, archive/reopen, and issue detail. Make identifiers globally unambiguous for nested GitLab namespaces.

Do not implement native external intake in this task.

Tests:
- Contract suite for every TrackerProtocol method.
- Label/status lifecycle, parent/dependency links, comment and metadata round trips, authorization rejection, pagination, and GitLab API failures.
- Existing GitHub tracker behavior remains unchanged.

Acceptance criteria:
- A GitLab Issues project can operate the entire Oompah task and epic lifecycle without GitHub code paths.
- Status safety and audit behavior match GitHub-backed tracking.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

