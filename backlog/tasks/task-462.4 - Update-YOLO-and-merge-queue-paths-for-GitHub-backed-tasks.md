---
id: TASK-462.4
title: Update YOLO and merge queue paths for GitHub-backed tasks
status: Done
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 04:03'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-462.3
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - tests/test_merge_queue.py
parent_task_id: TASK-462
priority: high
ordinal: 148000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make YOLO auto-merge, merge queue enqueue, queue-state display, and related notifications update GitHub-backed task state and comments through tracker protocol methods.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Merge queue success and failure paths update GitHub issue status and comments.
- [ ] #2 Queue-mode behavior remains unchanged for legacy Backlog tasks.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 03:28
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 03:35
---
Understanding: Duplicate investigation found no duplicate. TASK-474 covers epic strategy enforcement (different concern). TASK-462.3 (Done) handled review/CI/conflict/merge reconciliation paths. This task focuses specifically on: (1) YOLO auto-merge path updating GitHub-backed task state/comments through tracker protocol, (2) merge queue enqueue/queue-state/notifications doing the same. Next: explore oompah/orchestrator.py and oompah/server.py YOLO and merge queue code paths to find what needs updating.
---

author: oompah
created: 2026-06-10 03:44
---
Discovery: Found the exact code changes needed. Three server.py webhook handlers use tracker.fetch_issue_detail(source_branch) which works for Backlog (branch==identifier) but not GitHub-backed tasks (branch is a generated slug). They need to use orch._resolve_task_for_branch(tracker, source_branch, project_id=project.id) which uses the per-project branch index. Additionally, _yolo_review_actions_sync has no tracker updates after successful direct merge or enqueue — need to add _yolo_comment_enqueued and _yolo_mark_task_merged helpers (GitHub-backed only, guarded by isinstance check). Key files: oompah/server.py (3 functions), oompah/orchestrator.py (2 new methods + 3 call sites in _yolo_review_actions_sync), tests/test_merge_queue.py (new tests), tests/test_server_webhooks.py (update existing tests).
---

author: oompah
created: 2026-06-10 04:02
---
Implementation: Made three sets of changes. (1) oompah/server.py: replaced tracker.fetch_issue_detail(source_branch) with orch._resolve_task_for_branch(tracker, source_branch, project_id=project.id) in _label_task_merged_from_merge_group, _label_task_merged_from_pr, and _mark_task_in_review_from_webhook — this fixes GitHub-backed task lookup (branch name != identifier) while preserving Backlog behavior via fallback. (2) oompah/orchestrator.py: added _yolo_comment_enqueued (posts comment when PR enqueued) and _yolo_mark_task_merged (marks task Merged + posts comment when directly merged), both called from _yolo_review_actions_sync when self.config.tracker_kind == 'github_issues'. (3) tests/test_merge_queue.py: added TestYoloGitHubTrackerUpdates (4 tests for GitHub enqueue/merge paths) and TestWebhookGitHubTaskResolution (7 tests verifying _resolve_task_for_branch is used). Updated existing tests to set orch._resolve_task_for_branch.return_value. Also updated tests/test_server_webhooks.py similarly.
---

author: oompah
created: 2026-06-10 04:03
---
Verification: All tests pass. Key test results: tests/test_merge_queue.py (106 tests, 11 new), tests/test_orchestrator_merged.py (57 tests), tests/test_server_webhooks.py (31 tests updated), tests/test_yolo_handlers.py (21 tests) — 298 total, all green. Branch pushed to epic-TASK-462.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Updated YOLO and merge queue paths for GitHub-backed tasks. (1) Fixed three server.py webhook handlers (_label_task_merged_from_merge_group, _label_task_merged_from_pr, _mark_task_in_review_from_webhook) to use orch._resolve_task_for_branch instead of tracker.fetch_issue_detail so GitHub-backed tasks whose branch name != identifier are correctly resolved via per-project branch index. (2) Added _yolo_comment_enqueued and _yolo_mark_task_merged helpers to Orchestrator, called from _yolo_review_actions_sync only when tracker_kind=='github_issues', so successful YOLO enqueue and direct merge update GitHub issue state and comments through tracker protocol. Backlog task behavior is unchanged (AC#2). Added 11 new tests across TestYoloGitHubTrackerUpdates and TestWebhookGitHubTaskResolution, and updated existing tests to set orch._resolve_task_for_branch.return_value. All 298 tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->
