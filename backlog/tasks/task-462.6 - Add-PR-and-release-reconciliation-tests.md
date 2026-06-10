---
id: TASK-462.6
title: Add PR and release reconciliation tests
status: In Progress
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 05:36'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-462.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - tests
parent_task_id: TASK-462
priority: medium
ordinal: 150000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add regression coverage for branch-to-issue indexing, PR metadata writes, stale In Review recovery, CI-fix sibling tasks, merge conflicts, YOLO direct merge, merge queue enqueue, and release-pick outcomes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tests cover GitHub-backed and legacy Backlog-backed PR flows where behavior differs.
- [ ] #2 Release branch PRs are verified without relying on GitHub closing keywords.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 04:33
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-10 04:33
---
Focus: CI Failure Fixer
---

author: oompah
created: 2026-06-10 04:40
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-10 04:40
---
Focus: CI Failure Fixer
---

author: oompah
created: 2026-06-10 04:58
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-10 05:04
---
Understanding: This task requires adding regression tests for PR and release reconciliation flows. After reviewing git history, TASK-462.1-462.5 implemented: branch-to-issue indexing (github_tracker.py), PR metadata writes (orchestrator.py/tracker.py), stale In Review recovery, CI-fix sibling tasks, merge conflicts/YOLO/merge-queue (orchestrator.py/server.py), and release-pick GitHub paths (cherry_pick_pr_creator.py/release_pick_reconciler.py). The acceptance criteria require: (1) tests covering GitHub-backed vs Backlog-backed PR flow differences, (2) release branch PR tests without relying on GitHub closing keywords. Plan: examine the implementations added in 462.1-462.5, identify coverage gaps, and add targeted tests for each scenario.
---

author: oompah
created: 2026-06-10 05:24
---
Discovery: All existing tests (350) pass. The gaps for AC#1 and AC#2 are:\n1. Stale In Review recovery: No test for GitHub task where branch_name='oompah/proj/gh-42' and merged_branches contains that slug (not the identifier)\n2. CI-fix sibling: No test for _yolo_retry_ci finding GitHub task via branch index (all existing tests use Backlog-style branch==identifier)\n3. Merge conflict label clearing: Existing TestYoloMergeConflictLabelClearing uses fetch_issue_detail with Backlog-style; no test for GitHub-backed task cleared via branch index\n4. Release-pick AC#2: test_cherry_pick_pr_creator.py has no test verifying open_backport_pr does NOT include 'Fixes' keyword in description\n5. GitHub stale In Review kept-in-review: No test where branch_name keeps task In Review (as opposed to identifier)\nPlan: add tests/test_pr_reconciliation_github_vs_backlog.py covering all these gaps.
---

author: oompah
created: 2026-06-10 05:35
---
Implementation: Added tests/test_pr_reconciliation_github_vs_backlog.py with 34 tests covering all 8 areas from the task description. The tests specifically target behavior differences between GitHub-backed and Backlog-backed PR flows (AC#1): (1) Branch-to-issue indexing: GitHub via work_branch index vs Backlog via fetch_issue_detail; (2) PR metadata: oompah.work_branch only written for GitHub tasks; (3) Stale In Review: branch_name (work_branch slug) vs identifier for merged_branches/open_branches lookup; (4) CI-fix sibling: _yolo_retry_ci resolves GitHub task via branch index; (5) Merge conflict label clearing: uses branch index for GitHub tasks; (6) YOLO direct merge: _yolo_mark_task_merged explicitly marks GitHub tasks Merged (webhook can't resolve branch); Backlog tasks handled by webhook sweep instead; (7) Merge queue enqueue: stale merge-conflict label cleared via branch index; (8) Release-pick: open_backport_pr has no Fixes/Closes keywords in description (AC#2). All 34 new tests pass; 384 total tests pass.
---

author: oompah
created: 2026-06-10 05:36
---
Verification: All 34 new tests pass. Running full affected test suite: 384 tests pass (350 pre-existing + 34 new). No regressions. Pre-existing flaky test in test_github_tracker.py (asyncio OSError in unrelated test) is unrelated to changes and passes when run in isolation.
---
<!-- COMMENTS:END -->
