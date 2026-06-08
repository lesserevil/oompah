---
id: TASK-454.2
title: Honor task target branches when creating review PRs
status: In Progress
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 17:55'
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
<!-- COMMENTS:END -->
