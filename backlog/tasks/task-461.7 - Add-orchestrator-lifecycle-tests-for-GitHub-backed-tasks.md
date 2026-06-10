---
id: TASK-461.7
title: Add orchestrator lifecycle tests for GitHub-backed tasks
status: Done
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-10 09:49'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-461.6
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - tests
parent_task_id: TASK-461
priority: medium
ordinal: 143000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add focused tests for candidate fetch, dispatch, claim, worker exit, retry, close, reopen, verifier rejection, Needs Human, watcher-created tasks, and mixed Backlog/GitHub projects using mocked trackers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub-backed lifecycle tests do not require live GitHub network access.
- [ ] #2 Mixed tracker projects dispatch without cross-project task ID collisions.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 09:28
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 09:30
---
Understanding: TASK-461.7 is NOT a duplicate. Searched for similar tasks and found no overlap: TASK-457.4 covers tracker-protocol contract tests, test_mixed_tracker_regression.py covers API/server-level mixed tracker tests (filed under TASK-459.7). No existing test file covers orchestrator lifecycle with GitHub-backed tasks. Plan: implement tests/test_orchestrator_github_lifecycle.py covering candidate fetch, dispatch, claim, worker exit, retry, close, reopen, verifier rejection, Needs Human, watcher-created tasks, and mixed Backlog/GitHub projects using mocked trackers.
---

author: oompah
created: 2026-06-10 09:33
---
Discovery: Existing coverage in test_orchestrator_completion_verifier.py already covers GitHub worker exit (TestGitHubBackedWorkerExit) and verifier pass/fail flow (TestGitHubVerifierFlow). Need to add: (1) candidate fetch with GitHub projects, (2) dispatch+claim protocol (run-id stamp/verify/race abort), (3) _mark_needs_human routing to GitHub tracker, (4) retry scheduling with project_id, (5) mixed Backlog/GitHub dispatch without ID collision, (6) watcher-created tasks go to GitHub tracker. New file: tests/test_orchestrator_github_lifecycle.py
---

author: oompah
created: 2026-06-10 09:48
---
Implementation: Created tests/test_orchestrator_github_lifecycle.py with 40 focused tests across 9 test classes: (1) TestCandidateFetchGitHub - 6 tests for _fetch_all_candidates with GitHub projects; (2) TestMixedCandidateFetch - 4 tests for Backlog+GitHub mixed fetch without ID collisions (AC #2); (3) TestGitHubClaimProtocol - 6 tests for dispatch+claim run-ID stamp/verify/race abort; (4) TestMarkNeedsHumanGitHub - 4 tests for _mark_needs_human routing; (5) TestRetrySchedulingGitHub - 4 tests for _schedule_retry with project_id; (6) TestCloseReopenGitHub - 3 tests for close/reopen via tracker; (7) TestWorkerExitRetryGitHub - 3 tests for worker exit+retry path; (8) TestWatcherCreatedTasksGitHub - 5 tests for ErrorWatcher routing; (9) TestMixedProjectDispatch - 5 tests for mixed dispatch without ID collision. All use mocked trackers (no live GitHub network access, AC #1).
---

author: oompah
created: 2026-06-10 09:49
---
Verification: 40/40 tests pass in tests/test_orchestrator_github_lifecycle.py. Also verified no regressions in test_orchestrator_completion_verifier.py (14), test_error_watcher_orchestrator.py (5), test_mixed_tracker_regression.py (46) — 105 total tests pass. All tests use mocked trackers (no live GitHub network, AC #1). Mixed-tracker fetch and dispatch tests confirm no cross-project ID collision (AC #2).
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Delivered tests/test_orchestrator_github_lifecycle.py with 40 passing tests covering the full orchestrator lifecycle for GitHub-backed tasks: candidate fetch, dispatch+claim protocol (run-ID stamp/verify/race abort), Needs Human routing, retry scheduling with project_id, close/reopen via tracker, worker exit retry path, ErrorWatcher routing to GitHub tracker, and mixed Backlog/GitHub dispatch without ID collision. All tests use mocked trackers (no live GitHub network access, AC #1). Mixed-tracker tests confirm no cross-project task ID collision (AC #2). Not a duplicate: confirmed TASK-457.4 covers tracker-protocol contract tests and test_mixed_tracker_regression.py covers API-level mixed tests — this fills the orchestrator lifecycle gap.
<!-- SECTION:FINAL_SUMMARY:END -->
