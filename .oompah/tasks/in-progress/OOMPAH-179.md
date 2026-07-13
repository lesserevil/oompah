---
id: OOMPAH-179
type: task
status: In Progress
priority: 2
title: Reconcile release-addendum pull-request outcomes and controls
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-178
labels: []
assignee: null
created_at: '2026-07-13T02:35:55.903478Z'
updated_at: '2026-07-13T05:19:03.940210Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f666b1cb-d09b-4d75-9975-0a1875b8abb4
---
## Summary

Read sections 6 and 8 of plans/release-branch-addendums.md. Add PR polling that changes an in_review addendum to merged only after its target PR is merged and records completion evidence. A closed-unmerged PR must remain nonterminal until explicit retry; retry may change blocked or closed-unmerged in_review to open without changing commits. Add archive support for open/blocked only. Implement the retry/archive API endpoints, transition validation, cache invalidation, and oompah-authored source-task comments for state changes and errors. Tests: merged/open/closed PR outcomes; retry and archive authorization/transition errors; immutable snapshots across retries; duplicate poll idempotency; and comments. Acceptance: lifecycle controls are explicit and no replacement PR is opened automatically after a close.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

