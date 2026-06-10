---
id: TASK-462.2
title: Link PRs to central GitHub tasks and write review metadata
status: Done
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 03:06'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-462.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/scm.py
  - tests
parent_task_id: TASK-462
priority: high
ordinal: 146000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update PR body generation and review handoff so PRs reference the central GitHub issue, store Review URL and Review Number metadata, and avoid relying on closing keywords except where explicitly safe.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Opened PRs include a stable link to the central task hub issue.
- [ ] #2 Task metadata records source branch, target branch, PR number, and PR URL.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 02:02
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 02:03
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 03:00
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 03:02
---
Understanding: No duplicate found. TASK-458.5 built body-backed metadata read/write; TASK-462.1 built the branch-to-issue index. TASK-462.2 is the next step: (1) update PR body generation so opened PRs include a stable link to the central task hub issue (AC#1), (2) after creating a PR, write back review_url, review_number, and other metadata (source_branch, target_branch, PR number, PR URL) to the task (AC#2), (3) avoid closing keywords in PR bodies. Will explore orchestrator.py and scm.py to find the PR creation and review handoff code.
---

author: oompah
created: 2026-06-10 03:06
---
Discovery: Implementation was already in the working tree (uncommitted). Previous agent runs wrote the code but didn't commit. The changes are: (1) _build_pr_body() method in orchestrator.py - generates hub link using 'Relates to:' for cross-repo/release-branch cases, 'Fixes #N' only for same-repo+default-branch (the one case GitHub auto-close honours); (2) _write_review_metadata() method - best-effort writes of oompah.review_url, oompah.review_number, oompah.work_branch, oompah.target_branch; (3) _mark_task_in_review() updated to call _write_review_metadata after status update; (4) _ensure_review_exists() updated to pass description from _build_pr_body to create_review(); (5) Epic PR creation path also updated to include hub link and persist metadata; (6) tracker.py: review_url and review_number added to _KNOWN_BACKLOG_FIELDS; (7) 20 new tests in test_pr_body_and_review_metadata.py. All 20 tests pass.
---

author: oompah
created: 2026-06-10 03:06
---
Implementation: Committed and pushed to epic-TASK-462. Changes in oompah/orchestrator.py: (1) _build_pr_body() — generates hub issue link ('Relates to: [label](url)' for cross-repo/release-branch; 'Fixes #N\n\n[label](url)' only for same-repo+default-branch); (2) _write_review_metadata() — best-effort writes of oompah.review_url, oompah.review_number, oompah.work_branch, oompah.target_branch via tracker.set_metadata_field(); (3) _mark_task_in_review() — calls _write_review_metadata after update_issue(); (4) _ensure_review_exists() — passes description=pr_body to provider.create_review(); (5) epic PR open path also includes hub link and calls _write_review_metadata. tracker.py: oompah.review_url and oompah.review_number added to _KNOWN_BACKLOG_FIELDS. tests/test_pr_body_and_review_metadata.py: 20 new tests.
---

author: oompah
created: 2026-06-10 03:06
---
Verification: 20 new tests in test_pr_body_and_review_metadata.py all pass. Broader test suite (test_merge_queue.py, test_yolo_handlers.py, test_github_tracker.py, test_backlog_tracker.py) — 494 tests pass, 0 failures.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented _build_pr_body() (hub issue link with safe closing-keyword logic), _write_review_metadata() (best-effort oompah.review_url/number/work_branch/target_branch writes), updated _mark_task_in_review() and _ensure_review_exists() to use them, added review metadata writes to epic PR path, registered review_url/number in _KNOWN_BACKLOG_FIELDS. 20 new tests (494 total pass). Both ACs met: AC#1 hub link in all opened PRs; AC#2 review_url, review_number, work_branch, target_branch written to task metadata on PR creation.
<!-- SECTION:FINAL_SUMMARY:END -->
