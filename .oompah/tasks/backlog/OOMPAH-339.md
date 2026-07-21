---
id: OOMPAH-339
type: task
status: Backlog
priority: null
title: Enforce GitLab status-label authorization and audit/revert safety
parent: OOMPAH-323
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T23:24:47.554460Z'
updated_at: '2026-07-21T23:24:47.554460Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement GitLab parity for the GitHub status-label governance model in GitLabIssueTracker and its event/polling integration as required. Canonicalize status with exactly one oompah:status:* label; identify authorized actors; record trusted status transitions; reject/mark unauthorized label changes; audit and revert to the trusted status; and exclude issues under unresolved review from dispatch candidates. Preserve fallback/backfill and terminal archive semantics consistently with GitHub. Add tests for lifecycle transitions, authorized and unauthorized actors, successful and failed reverts, candidate suppression, audit comments/records, and API errors. Acceptance: status safety and audit behavior match the GitHub-backed tracker and no unauthorized GitLab label change can dispatch work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

