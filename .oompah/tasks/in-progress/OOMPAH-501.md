---
id: OOMPAH-501
type: bug
status: In Progress
priority: 1
title: Prevent premature epic rollup PR/MR creation from child close handoffs
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T14:01:32.048881Z'
updated_at: '2026-07-28T14:11:42.517390Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 48afbf9e-aa7e-4d48-af33-bafcd2662217
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
author: oompah
created: 2026-07-28 14:10
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 0, Tool calls: 12
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 29s
- Log: OOMPAH-501__20260728T140906Z.jsonl
---
author: oompah
created: 2026-07-28 14:10
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 14:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 14:11
---
Discovery: Duplicate screening found no confirmed duplicate. OOMPAH-443 added the canonical child-state/landing-evidence gate used by _open_epic_main_prs and the final YOLO merge check, but it did not make check_close_gate parent-aware. OOMPAH-309/OOMPAH-404 hardened the separate automatic review-handoff path when parent resolution fails, but did not change the generic close gate or its gh-specific refusal diagnostic. OOMPAH-165 addressed premature parent Merged state/target validation, and OOMPAH-219 addressed shared-worktree commit absorption; neither covers review creation during child close. OOMPAH-452 confirms the new path-specific regression: its Done child close on epic-OOMPAH-451 was refused while OOMPAH-456 remained Open, inducing PR #558. OOMPAH-501 is therefore distinct follow-up work.
---
<!-- COMMENTS:END -->
