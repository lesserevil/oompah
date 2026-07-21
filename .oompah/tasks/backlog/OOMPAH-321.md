---
id: OOMPAH-321
type: task
status: Backlog
priority: 1
title: Complete GitLab Merge Request provider parity
parent: OOMPAH-318
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T20:33:51.110283Z'
updated_at: '2026-07-21T20:33:51.110283Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, GitLab implementation.

Implement GitLabProvider against the forge-neutral SCM contract for GitLab.com and configurable GitLab 17+ hosts. Handle nested namespace project IDs, URL encoding, pagination, retries, rate limits, redacted errors, MR list/detail/find/create/rebase/merge/close, labels, notes, changed files, commits, reviewers, approvals, draft/WIP, conflicts, divergence, and mergeability. Preserve history: do not force squash. Implement normal GitLab auto-merge through merge_when_pipeline_succeeds; return actionable policy/approval errors and do not implement merge trains.

Tests:
- HTTP fixtures for GitLab.com and self-managed base URL/nested namespace requests.
- Every SCM contract operation, pagination, auth failure, conflict, unavailable MR, label preservation, history-preserving merge, and auto-merge rejection.

Acceptance criteria:
- GitLab MRs behave equivalently to GitHub PRs for all supported SCM operations.
- No request leaks an access token in logs or errors.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

