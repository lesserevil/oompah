---
id: TASK-460.4
title: Add guards against new Backlog task files in GitHub-backed work
status: Done
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-10 05:19'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.3
  - TASK-460.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - tests/test_completion_verifier.py
parent_task_id: TASK-460
priority: high
ordinal: 134000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Detect and reject new backlog/tasks or backlog/completed files created during GitHub-backed task runs. Surface clear completion-verifier failures, dashboard alerts, and optional PR-check guidance instead of silently accepting a second task source.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub-backed tasks fail verification if they add Backlog task files.
- [ ] #2 The guard does not block legacy Backlog task updates.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 04:51
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 04:57
---
Understanding: Not a duplicate — no existing task covers guarding against new Backlog task files in GitHub-backed work. TASK-460.1 (Done) built the oompah task CLI; TASK-460.2 (Done) updated prompts; TASK-460.3 (In Progress) routes follow-ups. TASK-460.4 specifically adds a completion-verifier check that rejects GitHub-backed runs if they produce new backlog/tasks or backlog/completed files. Plan: (1) read plans/github-issues-tracker-migration.md for spec, (2) find the completion verifier in orchestrator.py, (3) add a guard that checks git diff for new backlog/tasks|completed files when tracker_kind==github_issues, (4) surface failure clearly, (5) add tests in tests/test_completion_verifier.py.
---

author: oompah
created: 2026-06-10 05:00
---
Discovery: No duplicate. Key files: oompah/completion_verifier.py (VerifierResult, verify_completion), oompah/orchestrator.py (_run_completion_verifier, _alerts). Issue model already has tracker_kind field (added by TASK-459.3). Plan: (1) add detect_new_backlog_files() + compute_added_files() to completion_verifier.py; (2) add new_backlog_files field to VerifierResult + update render_rejection_comment; (3) gate check on tracker_kind==github_issues in verify_completion BEFORE skip rules (so epic/ci-fix labels don't bypass it); (4) update orchestrator._run_completion_verifier logging + add dashboard alert when new_backlog_files fires; (5) add tests for AC#1 (rejected) and AC#2 (legacy not blocked).
---

author: oompah
created: 2026-06-10 05:18
---
Implementation: (1) oompah/completion_verifier.py — added _BACKLOG_GUARD_PREFIXES constant (backlog/tasks/, backlog/completed/); added compute_added_files() using --diff-filter=A to find only newly-created files; added detect_new_backlog_files() to filter paths matching the guard prefixes; added new_backlog_files: list[str] field to VerifierResult; updated render_rejection_comment() to surface new backlog files with a pointer to oompah task create; updated verify_completion() to run the guard BEFORE standard skip rules (so epic/ci-fix labels cannot bypass it) — gated on tracker_kind==github_issues — fails open on git errors. (2) oompah/orchestrator.py — updated _run_completion_verifier logging to include new_backlog_files; added dashboard alert keyed on backlog_file_guard:<identifier> when guard fires so operators can see violations in the dashboard. (3) tests/test_completion_verifier.py — added TestDetectNewBacklogFiles (6 tests), TestComputeAddedFiles (4 tests), TestNewBacklogFilesGuard (13 tests covering AC#1, AC#2, and rejection comment), updated imports.
---

author: oompah
created: 2026-06-10 05:18
---
Verification: 78 tests in tests/test_completion_verifier.py pass (includes 24 new tests). 6 tests in test_orchestrator_completion_verifier.py pass. AC#1 verified by test_github_adds_backlog_task_file_rejected, test_github_adds_backlog_completed_file_rejected, test_guard_fires_before_skip_rules_epic/ci_fix. AC#2 verified by test_legacy_backlog_task_none_tracker_kind_not_blocked, test_legacy_backlog_md_tracker_kind_not_blocked.
---

author: oompah
created: 2026-06-10 05:19
---
Completion: Delivered backlog-file guard for GitHub-backed tasks. (1) completion_verifier.py: compute_added_files() + detect_new_backlog_files() detect newly-created backlog/tasks/ and backlog/completed/ files; verify_completion() runs the guard before skip rules when tracker_kind==github_issues; VerifierResult.render_rejection_comment() surfaces clear guidance to use oompah task create instead. (2) orchestrator.py: _run_completion_verifier logs new_backlog_files and adds a backlog_file_guard dashboard alert per issue. (3) 24 new tests; all 78 test_completion_verifier tests pass. Both ACs met: GitHub-backed tasks fail if Backlog files added; legacy tasks not affected.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added backlog-file guard to completion_verifier.py: compute_added_files() + detect_new_backlog_files() detect newly-created backlog/tasks/ and backlog/completed/ files for GitHub-backed tasks (tracker_kind==github_issues); verify_completion() runs the guard before skip rules; render_rejection_comment() surfaces clear guidance. Updated orchestrator._run_completion_verifier to log and add dashboard alert. 24 new tests, all 78 test_completion_verifier tests pass. Both ACs met.
<!-- SECTION:FINAL_SUMMARY:END -->
