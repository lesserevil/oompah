---
id: OOMPAH-451
type: epic
status: In Validation
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
updated_at: '2026-08-04T15:19:10.645863Z'
work_branch: epic-OOMPAH-451
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/560
review_number: '560'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/560
oompah.review_number: '560'
oompah.work_branch: epic-OOMPAH-451
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c9d9897dbd67
    project_id: proj-14849f1b
    task_id: OOMPAH-451
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ec2faf89a761d26e33c737e46d2bbf72c87afc3f6eb9eef479e9cd305f0777df
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T15:19:04.185104+00:00'
  attempt_history: []
---
## Summary

Problem: OOMPAH-318 was merged to main at a4975ea71 before later child work completed. Six accepted child tasks are recorded as Merged, but the implementation commits remain only on origin/epic-OOMPAH-318. Current main lacks oompah/gitlab_tracker.py, GitLabHookManager, most GitLab webhook event parsing, and lifecycle wiring. The first live GitLab project exposed these gaps.

Scope: recover the still-required GitLab capabilities from commits 24ae25693, 696d5bfaa, 2b3312672, 4302b74e8, and 62cde900b by reconciling them selectively onto current main. Do not merge the stale epic branch wholesale because it is hundreds of commits behind and would revert unrelated current work. Include the project-editor regression discovered during live onboarding.

Tests: run focused tracker, webhook, project CRUD/UI, forge-isolation, lifecycle, and cross-forge acceptance suites, then make test.

Acceptance criteria: a GitLab managed project can be added, edited, state-branch enabled, polled, receive authenticated hooks, use GitLab Issues when configured, and exercise MR/pipeline workflows without invoking GitHub-only APIs or subprocesses; all recovered task state reflects code actually reachable from main.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 14:18
---
Closed premature PR #558 because this epic is not ready to merge while OOMPAH-456 remains in progress. Preserved epic-OOMPAH-451 for the remaining child work. OOMPAH-501/PR #559 prevents child close handoffs from creating a rollup review and rechecks the full epic readiness immediately before provider review creation; a fresh epic-owned PR will be created only after the entire branch is ready.
---
author: oompah
created: 2026-08-04 15:19
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
