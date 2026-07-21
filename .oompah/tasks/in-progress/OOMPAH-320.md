---
id: OOMPAH-320
type: task
status: In Progress
priority: 1
title: Define a forge-neutral SCM and CI provider contract
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-319
labels: []
assignee: null
created_at: '2026-07-21T20:33:50.132513Z'
updated_at: '2026-07-21T22:47:59.138485Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 0c4bedbe-7050-413d-8dce-166bdf3cfbb7
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, Core architecture and interfaces.

Refactor SCMProvider and normalized review/CI types so GitHub and GitLab use one explicit contract. Cover review state, labels, comments, files, commits, branch head, commit CI status, review creation/rebase/merge/close, and ordinary auto-merge. Define passed, failed, pending, and unknown CI states plus structured capability warnings. Move shared consumers only to contract methods; retain GitHub behavior.

Do not add GitLab REST endpoint implementations beyond test doubles in this task.

Tests:
- Contract test fixtures run against a fake provider and existing GitHub provider.
- Missing optional capabilities degrade to unknown/warnings rather than exceptions.
- Existing review, release, YOLO, churn, and close-gate tests remain green.

Acceptance criteria:
- No workflow consumer needs GitHub-specific provider methods for supported behavior.
- Contract documents error and unavailable-capability semantics in code.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:47
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:47
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
