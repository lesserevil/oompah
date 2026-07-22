---
id: OOMPAH-326
type: task
status: In Progress
priority: 1
title: Integrate GitLab SCM and pipelines into review, YOLO, and release delivery
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-321
- OOMPAH-322
labels: []
assignee: null
created_at: '2026-07-21T20:34:28.175529Z'
updated_at: '2026-07-22T00:29:50.736427Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: da9723a5-6b46-4402-8f24-332b389e8644
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, Core architecture and GitLab implementation.

Update orchestrator, review queue, close/landing gates, churn checks, backport/release-pick reconciliation, release addendums, Release Delivery, and post-merge CI remediation to use forge-neutral SCM and CI contracts. GitLab MRs must open from Oompah work branches, show normalized pipeline progress, auto-merge only through merge_when_pipeline_succeeds, preserve history, and create a remediation task after target-branch pipeline failure. Explicitly surface merge trains as unsupported.

Tests:
- GitLab fake-provider flows for normal review, failed/pending CI, rebase/conflict, auto-merge rejection, merge outcome, branch protection, selected release delivery, and release CI remediation idempotency.
- GitHub regression tests for these flows.

Acceptance criteria:
- GitLab managed projects support the same Oompah review/release workflows as GitHub without provider-specific orchestration branches.
- A failed GitLab release pipeline produces one actionable remediation task.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 00:29
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 00:29
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 00:29
---
Understanding: I will perform the required duplicate screening for GitLab SCM/pipeline parity, review candidate tasks in full, and either archive this task as a confirmed duplicate or leave a focused handoff for implementation.
---
<!-- COMMENTS:END -->
