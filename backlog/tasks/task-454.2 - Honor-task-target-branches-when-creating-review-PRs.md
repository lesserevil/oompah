---
id: TASK-454.2
title: Honor task target branches when creating review PRs
status: Done
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 17:56'
labels:
  - task
dependencies:
  - TASK-454.1
parent_task_id: TASK-454
priority: high
ordinal: 92000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update review handoff so normal per-task PRs target Issue.target_branch when present, falling back to the project default branch. Preserve epic stacked/shared behavior and add tests proving release tasks open PRs into release branches.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 17:45
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 17:51
---
Understanding: This is NOT a duplicate. TASK-454.1 (Done) added Issue.target_branch to the data model; TASK-454.2 needs to USE that field when creating review PRs - normal per-task PRs should target Issue.target_branch, falling back to the project default branch. Epic stacked/shared behavior must be preserved. Plan: (1) find where review PRs are created (likely in projects.py or a review/handoff module), (2) update the PR creation to check Issue.target_branch first, (3) add tests proving release tasks open PRs into release branches.
---

author: oompah
created: 2026-06-08 17:53
---
Discovery: Key code is in oompah/orchestrator.py _ensure_review_exists() around line 4354. Currently sets target_branch = project.default_branch, then overrides for stacked epics. Change needed: add elif entry.issue and entry.issue.target_branch: target_branch = entry.issue.target_branch after the stacked-epic block. This preserves shared (returns early, no PR) and stacked (uses epic branch) behavior while making flat/top-level tasks honor Issue.target_branch. Existing tests in tests/test_epic_strategy.py::TestEnsureReviewExistsRespectsEpicStrategy cover the current behaviors. Need new tests for target_branch field.
---

author: oompah
created: 2026-06-08 17:55
---
Implementation: Modified oompah/orchestrator.py _ensure_review_exists() to add an 'elif entry.issue and entry.issue.target_branch: target_branch = entry.issue.target_branch' clause after the stacked-epic block. This means: (1) shared+parent_epic: still returns early with no PR, (2) stacked+parent_epic: still targets the epic branch, (3) all others: uses Issue.target_branch if set, else project.default_branch. Added 4 new tests in TestEnsureReviewExistsRespectsEpicStrategy: test_task_target_branch_used_when_set, test_task_without_target_branch_falls_back_to_project_default, test_release_task_opens_pr_into_release_branch, test_stacked_child_with_target_branch_still_uses_epic_branch.
---

author: oompah
created: 2026-06-08 17:55
---
Verification: All 78 tests in test_epic_strategy.py pass (including 4 new TASK-454.2 tests). 194/194 tests pass in test_backlog_tracker.py + test_orchestrator_handlers.py. No regressions.
---

author: oompah
created: 2026-06-08 17:56
---
Completion: Updated oompah/orchestrator.py _ensure_review_exists() to honor Issue.target_branch when creating review PRs. Normal per-task PRs now target Issue.target_branch when set (e.g. release/2.3), falling back to project.default_branch. Stacked epic children still target the epic branch. Shared epic children still skip per-child PR creation. 4 new tests added, all 78 tests in test_epic_strategy.py pass. Code pushed to epic-TASK-454.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Updated _ensure_review_exists() in oompah/orchestrator.py to honor Issue.target_branch when creating review PRs: tasks with target_branch set (e.g. release/2.3) open PRs into that branch; fall back to project.default_branch when unset. Stacked epic behavior preserved (children still target epic branch). Shared epic behavior preserved (no per-child PR). 4 new tests added in test_epic_strategy.py, all 78 tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->
