---
id: OOMPAH-426
type: bug
status: In Progress
priority: 1
title: Block child task PRs from merging to main before their epic completes
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T21:15:59.630196Z'
updated_at: '2026-07-23T21:24:09.661939Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9b589287-01b3-4ddc-8498-b37e946c13ba
---
## Summary

Bug observed on EXOCOMP-57: although it is a child of still-open epic EXOCOMP-9 in a shared-epic project, it opened and YOLO-merged PR #1 directly from EXOCOMP-57 to main. Enforce the merge gate so a non-terminal child task with a parent epic cannot create, approve, or merge a PR targeting the project target branch/main; child work must land on the parent epic branch and only the completed epic may merge to main. Cover PR creation, YOLO merge/reconciliation, and any branch/work_branch override path with regression tests reproducing EXOCOMP-57. Ensure a clear Needs Human handoff if an existing invalid PR requires operator action. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 21:16
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 21:16
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 21:23
---
Understanding: Investigating OOMPAH-426 as Duplicate Investigator. The bug describes EXOCOMP-57, a child of still-open epic EXOCOMP-9 in a shared-epic project, which opened and YOLO-merged PR #1 directly from EXOCOMP-57 to main, bypassing the epic branch gate.
---
author: oompah
created: 2026-07-23 21:24
---
Discovery: Duplicate screening complete — NO confirmed duplicate found.

Scope searched:
- All .oompah/tasks/ (archived, backlog, done, merged, open) — 200+ tasks
- oompah/ source tree for relevant functions (_yolo_epic_strategy_block_reason, _ensure_review_exists, _close_invalid_epic_policy_review, shared_epic)
- Git log for related commits
- Candidate tasks reviewed via oompah task view

Closest candidates reviewed and ruled out as duplicates:

**OOMPAH-307 (Merged)**: 'Keep shared-epic child work and merge state on the epic branch' — This is the parent epic that covers the SAME CATEGORY of bug (OOMPAH-286/PR #466 pattern: child assigned own branch + PR to main). However, OOMPAH-307 and ALL its children (308, 309, 310, 311, 312, 313) were completed and merged. OOMPAH-426 describes a REGRESSION — the bug recurring on a different project (EXOCOMP) after OOMPAH-307 fixes were applied. NOT a duplicate.

**OOMPAH-309 (Merged)** / **OOMPAH-404 (Merged)**: Hardened 3 orchestrator.py call sites to fail-closed when _resolve_parent_epic returns None for a child with parent_id. Covers the tracker-error path but not all bypass paths. OOMPAH-426 may indicate a gap not covered by OOMPAH-404.

**OOMPAH-412 (Merged)** / **OOMPAH-413 (Merged)**: Audited and added regression tests for shared-epic Merged promotion paths. Covered _reconcile_merged_epic_children, _label_merged_epics, etc. but not PR creation/YOLO merge gates for child tasks with work_branch override.

**OOMPAH-313 (Merged)**: Regression tests for OOMPAH-285/286 routing. Notably found _resolve_task_for_branch raises → gate fails OPEN (intentional for unrelated PRs). This may be the surviving gap EXOCOMP-57 exploits.

Key differentiator: OOMPAH-426 explicitly mentions 'branch/work_branch override path' which suggests a code path where the child's work_branch or branch is explicitly set/overridden to a non-epic branch (e.g., 'EXOCOMP-57' instead of 'epic-EXOCOMP-9'), and this override is not caught by the existing gates.

Relevant code locations:
- oompah/orchestrator.py: _yolo_epic_strategy_block_reason (~line 12090), _close_invalid_epic_policy_review (~line 12174), _ensure_review_exists (~line 8138), _create_workspace_for_issue (~line 5000)
- tests/test_epic_strategy.py: TestYoloEpicStrategyBlockReason, TestCloseInvalidEpicPolicyReview, TestEnsureReviewExistsRespectsEpicStrategy
- models.py line 26: comment references OOMPAH-286/PR #466 as the known bypass pattern
---
<!-- COMMENTS:END -->
