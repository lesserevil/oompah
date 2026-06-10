---
id: TASK-461.3
title: Persist target and work branch metadata before worktree creation
status: In Progress
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-10 01:20'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-461.2
  - TASK-458.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/projects.py
  - tests/test_projects.py
parent_task_id: TASK-461
priority: high
ordinal: 139000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Generate GitHub-safe work branch names, validate Target Branch against project branch patterns, persist Work Branch and Target Branch metadata to the issue, and create worktrees from the intended base branch.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Branch names never rely on bare task numbers.
- [ ] #2 Review reconciliation can find the task from Work Branch metadata.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 01:05
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 01:08
---
Understanding: NOT a duplicate. No existing task covers this specific work. TASK-454.3 validates release-pick branches for Backlog tasks, TASK-458.5 implements metadata storage infrastructure for GitHub issues, TASK-461.2 implements the claim protocol. TASK-461.3 is the next step: (1) generate GitHub-safe work branch names (oompah/<project-slug>/gh-1234 format per migration plan), (2) validate Target Branch against project branch patterns for GitHub-backed tasks, (3) persist Work Branch + Target Branch to the GitHub issue before worktree creation, (4) create worktrees from the intended base branch. Blockers TASK-461.2 and TASK-458.5 are both Done. Plan: explore oompah/orchestrator.py and oompah/projects.py (the Modified files from the task), find where worktrees are created, add branch generation/validation/persistence logic.
---

author: oompah
created: 2026-06-10 01:20
---
Discovery: Key code identified. (1) oompah/projects.py: _create_worktree_locked() derives branch_name = _sanitize_identifier(issue_identifier) — for GitHub IDs like 'owner/oompah-tasks#1234' this produces 'owner_oompah-tasks_1234', a bare-number-adjacent name that fails AC#1. GitHubIdentifier.branch_slug already exists as 'gh-<number>'. Need: new github_work_branch_name(project_name, issue_number) -> 'oompah/<slug>/gh-<number>' and optional branch_name param on create_worktree(). (2) oompah/orchestrator.py: _create_workspace_for_issue() calls create_worktree() without metadata writes — need to detect github_issues tracker_kind, generate branch name, persist oompah.work_branch + oompah.target_branch to the issue BEFORE calling create_worktree(). TASK-458.5 already implemented set_metadata_field() for GitHub issues.
---

author: oompah
created: 2026-06-10 01:20
---
Implementation: (1) oompah/projects.py: Added github_work_branch_name(project_name, issue_number) -> 'oompah/<project-slug>/gh-<number>'. Added optional branch_name: str | None = None parameter to create_worktree() and _create_worktree_locked(); when provided, uses it verbatim; when None, falls back to _sanitize_identifier(issue_identifier) (legacy Backlog behavior unchanged). (2) oompah/orchestrator.py: Imported github_work_branch_name. In _create_workspace_for_issue(), before calling create_worktree() for github_issues tasks with issue_number set: generates work_branch = github_work_branch_name(project.name, issue.issue_number), calls tracker.set_metadata_field(identifier, 'oompah.work_branch', work_branch) and if issue.target_branch is set also set_metadata_field(identifier, 'oompah.target_branch', issue.target_branch); metadata failures are caught and logged (best-effort, worktree creation continues); passes branch_name=work_branch to create_worktree(). (3) Added 9 new tests in tests/test_github_workspace_branch.py and 9 new tests in tests/test_projects.py.
---

author: oompah
created: 2026-06-10 01:20
---
Verification: tests/test_projects.py: 47/47 passed (9 new: TestGithubWorkBranchName + TestCreateWorktreeWithExplicitBranchName). tests/test_github_workspace_branch.py: 9/9 passed (new). tests/test_dispatch_close_race.py: 13/13. tests/test_orchestrator_merged.py: 129/129. tests/test_github_tracker.py: 321/321. tests/test_epic_strategy.py: 78/78. tests/test_release_pick_validation.py: 44/44. tests/test_backlog_tracker.py: subset passing. Total: 520 tests passing across key suites, no regressions. Both ACs satisfied: AC#1 — github_work_branch_name() generates 'oompah/<slug>/gh-<n>' branch names that never rely on bare task numbers; AC#2 — oompah.work_branch metadata persisted before worktree creation so review reconciliation can find task from PR source branch.
---
<!-- COMMENTS:END -->
