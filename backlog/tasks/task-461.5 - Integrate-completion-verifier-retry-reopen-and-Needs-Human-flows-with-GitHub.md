---
id: TASK-461.5
title: >-
  Integrate completion verifier, retry, reopen, and Needs Human flows with
  GitHub
status: In Progress
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-10 02:12'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-461.4
  - TASK-458.4
  - TASK-458.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - tests
parent_task_id: TASK-461
priority: high
ordinal: 141000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update verifier rejection comments, reopen operations, pending retry cancellation, Needs Human marking, cost metadata, and question-answer flows to write through the tracker protocol and support GitHub-backed tasks.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Verifier pass/fail flows update GitHub issue comments and status.
- [ ] #2 Retry and manual close races are covered for GitHub-backed tasks.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 01:53
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 01:55
---
UNDERSTANDING: This is NOT a duplicate. TASK-461.5 is the 5th subtask of the GitHub Issues migration epic (TASK-461). All blockers are Done (TASK-461.4: worker-exit GitHub gate, TASK-458.4: GitHub create/update/comment/labels, TASK-458.5: GitHub metadata). This task must update verifier rejection comments, reopen ops, retry cancellation, Needs Human marking, cost metadata, and Q&A flows to route through the tracker protocol (so GitHub-backed tasks get GitHub comments/status updates instead of Backlog file writes). Plan: (1) Read orchestrator.py and server.py to find all hardcoded Backlog write paths in verifier/retry/reopen/needs-human/Q&A flows, (2) Route each through tracker.add_comment/update_issue/mark_needs_human, (3) Write tests per AC #1 and #2. Proceeding to discovery.
---

author: oompah
created: 2026-06-10 02:06
---
DISCOVERY: The implementation is already correct — verifier rejections, reopen ops, retry cancellation, Needs Human marking, cost metadata, and Q&A flows all route through the tracker protocol in orchestrator.py and server.py. The code uses tracker.reopen_issue(), tracker.add_comment(), tracker.update_issue(), tracker.set_metadata_field() and _mark_needs_human() which all work with GitHubIssueTracker. What's MISSING are tests covering GitHub-backed tasks specifically for: (1) verifier pass/fail flows (AC #1) — no GitHub-specific verifier tests in test_orchestrator_completion_verifier.py; (2) retry/manual close races (AC #2) — TestUiCloseCancelsPendingRetry only tests Backlog identifiers, no GitHub identifier variant. Plan: add TestGitHubVerifierFlow to test_orchestrator_completion_verifier.py and TestGitHubManualCloseRace to test_dispatch_close_race.py.
---

author: oompah
created: 2026-06-10 02:12
---
IMPLEMENTATION: Added tests for both ACs. (1) AC #1 — Added TestGitHubVerifierFlow (5 tests) to test_orchestrator_completion_verifier.py: verifier rejection calls tracker.reopen_issue() on the GitHub tracker; diagnostic comment posted via tracker.add_comment(); verifier pass honors close; max-rejections fail-open path; retry scheduled with GitHub identifier (owner/repo#N). (2) AC #2 — Added TestGitHubManualCloseRace (4 tests) to test_dispatch_close_race.py: GitHub pending retry cancelled on manual close (using issue_key body field for slashed identifier); retry cancelled on terminal Done status update; dispatch aborts for closed GitHub issue; any non-in_progress status change cancels the retry. Also updated the _write_task_cost_record docstring to clarify it works via tracker protocol for both Backlog and GitHub backends.
---
<!-- COMMENTS:END -->
