---
id: OOMPAH-501
type: bug
status: Open
priority: 1
title: Prevent premature epic rollup PR/MR creation from child close handoffs
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T14:01:32.048881Z'
updated_at: '2026-07-28T14:09:49.500422Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3d6ebe0f-b54c-4b10-94e3-feb0963d1813
---
## Summary

Triggered by: OOMPAH-452

Problem: PR #558 was created from epic-OOMPAH-451 to main while child OOMPAH-456 was incomplete. OOMPAH-452 correctly worked on the shared epic branch, but the generic close gate saw commits ahead of main and instructed a maintenance agent to run gh pr create. This bypassed the existing OOMPAH-443 rollup-readiness gate. An early rollup review is confusing, carries child-specific metadata, and interferes with safe rebasing of the still-active shared branch.

Implementation scope: make review non-creation a hard invariant for incomplete epic branches across GitHub PRs and GitLab MRs. A child completing on a shared epic branch must be allowed to reach Done without requiring or creating a review to the project target branch. The close gate must recognize parent-owned shared work and must not emit PR/MR creation instructions. Centralize or reuse the canonical epic rollup readiness check so every automatic review-creation path refuses to create the rollup review until all actionable children, including nested epics, have the required state and landing evidence. Preserve standalone-task review handoff and the final YOLO merge-time recheck. Do not close or mutate an unrelated pre-existing review as part of this implementation. Relevant files include oompah/close_gate.py, oompah/orchestrator.py, tests/test_close_gate.py, and tests/test_epic_strategy.py.

Required tests: reproduce OOMPAH-452/PR #558 with a Done child on epic-OOMPAH-451 and an Open sibling; assert the child close succeeds without any review and without a create-review instruction. Assert the rollup creator makes no provider call while any normal child is incomplete, while a nested child epic is not Merged, or while landing evidence is missing. Assert it creates exactly one review after the entire branch is ready. Retain standalone task close/review tests and the merge-time readiness tests. Run focused tests and make test.

Acceptance criteria: no PR/MR from an epic branch to its target branch exists before the whole branch is ready to merge; child completion on the shared branch never requires a review; nested epic readiness is honored; review creation occurs once after readiness and remains provider-neutral; diagnostics do not tell agents or humans to create a premature review; all tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 14:01
---
Manual implementation started. Root cause confirmed: check_close_gate evaluates a shared child work_branch against the project default branch without parent/epic context, refuses the child close, and emits a forge-specific create-PR command. The existing canonical epic-rollup readiness gate covers normal automated creation and final merging but is bypassed when an agent follows this refusal instruction. Implementing parent-aware close handling plus regression coverage now.
---
author: oompah
created: 2026-07-28 14:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 14:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 14:09
---
Understanding: Screening OOMPAH-501 for duplication before any implementation. I will search prior tasks for epic rollup readiness, shared epic branches, close-gate review creation, and the referenced OOMPAH-443/OOMPAH-452 history; then read the closest candidates in full and either archive as a confirmed duplicate or hand off for implementation.
---
<!-- COMMENTS:END -->
