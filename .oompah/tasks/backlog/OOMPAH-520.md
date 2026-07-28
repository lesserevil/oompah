---
id: OOMPAH-520
type: task
status: Backlog
priority: null
title: Re-run the branch quality gate when an open review head changes
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T17:49:18.823929Z'
updated_at: '2026-07-28T17:49:21.474489Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem: _open_epic_main_prs returns through _ensure_epic_in_review_metadata as soon as it finds an existing open epic PR/MR. If a repair commit is pushed after initial review creation, _review_quality_gate_passes is never called for the new exact HEAD even though docs/branch-quality-gates.md promises that a new commit or rebase causes a new run. Forge CI still runs, but the persistent local full-gate invariant and exact-SHA evidence are stale. Implementation: in oompah/orchestrator.py, gate the existing-open-review reconciliation path with _review_quality_gate_passes using the resolved project, epic source branch, and target branch. Reuse cached pass evidence for the same key, run exactly once for a changed head, keep the review open but block YOLO through the existing Needs CI Fix transition on failure, and avoid duplicate comments/runs. Tests: extend tests/test_epic_strategy.py and tests/test_quality_gate.py for existing review unchanged-head reuse, changed-head rerun, failure behavior, and no duplicate review creation. Run focused suites and make test. Acceptance criteria: every open epic review's current head has passing exact-head local evidence before metadata/YOLO reconciliation proceeds; unchanged heads do not rerun; new commits and rebases do; PR #564 remains blocked until the new head passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 17:49
---
Claimed by the current Codex session as an exact-head regression discovered while repairing PR #564. Held from dispatch while I implement it on epic-OOMPAH-502.
---
<!-- COMMENTS:END -->
