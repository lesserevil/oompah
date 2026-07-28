---
id: OOMPAH-451
type: epic
status: In Review
priority: 1
title: Restore GitLab parity stranded after the OOMPAH-318 epic merge
parent: null
children:
- OOMPAH-452
- OOMPAH-453
- OOMPAH-454
- OOMPAH-455
- OOMPAH-456
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T12:34:07.972119Z'
updated_at: '2026-07-28T13:05:36.652595Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem: OOMPAH-318 was merged to main at a4975ea71 before later child work completed. Six accepted child tasks are recorded as Merged, but the implementation commits remain only on origin/epic-OOMPAH-318. Current main lacks oompah/gitlab_tracker.py, GitLabHookManager, most GitLab webhook event parsing, and lifecycle wiring. The first live GitLab project exposed these gaps.

Scope: recover the still-required GitLab capabilities from commits 24ae25693, 696d5bfaa, 2b3312672, 4302b74e8, and 62cde900b by reconciling them selectively onto current main. Do not merge the stale epic branch wholesale because it is hundreds of commits behind and would revert unrelated current work. Include the project-editor regression discovered during live onboarding.

Tests: run focused tracker, webhook, project CRUD/UI, forge-isolation, lifecycle, and cross-forge acceptance suites, then make test.

Acceptance criteria: a GitLab managed project can be added, edited, state-branch enabled, polled, receive authenticated hooks, use GitLab Issues when configured, and exercise MR/pipeline workflows without invoking GitHub-only APIs or subprocesses; all recovered task state reflects code actually reachable from main.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

