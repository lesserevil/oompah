---
id: TASK-462.1
title: Build branch-to-issue index from tracker metadata
status: In Progress
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 01:57'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-461.3
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - tests/test_merge_queue.py
parent_task_id: TASK-462
priority: high
ordinal: 145000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace source-branch-to-task lookup that assumes branch names equal Backlog identifiers. Build a per-project index from GitHub Work Branch metadata and open/in-review issues, with legacy fallback for Backlog branches.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CI-fix and merge-conflict flows can resolve GitHub-backed tasks from PR source branches.
- [ ] #2 Legacy Backlog branch lookup continues to work.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 01:39
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 01:40
---
Understanding: This task requires replacing the branch-name=task-ID assumption in source-branch-to-task lookups. Need to build a per-project index from GitHub Issue Work Branch metadata (field persisted by TASK-461.3) and open/in-review issues. Legacy fallback for Backlog branches where branch name == task ID should remain. No duplicate found after searching for 'branch-to-issue index', 'branch lookup', 'github work branch', 'task lookup', and 'PR source branch'. Proceeding with investigation.
---

author: oompah
created: 2026-06-10 01:48
---
Discovery: Found the key code. _resolve_task_for_branch (orchestrator.py:7871) calls tracker.fetch_issue_detail(source_branch) assuming branch==identifier (Backlog convention). For GitHub tasks, branches are like oompah/proj/gh-1234. Solution: (1) Add work_branch:str|None to Issue model, (2) populate it from body metadata in _gh_issue_to_issue, (3) add _build_branch_index per-project that fetches open/in-review issues and maps work_branch→identifier, (4) update _resolve_task_for_branch to check index first with legacy fallback, (5) update _clear_merge_conflict_label_for_branch similarly. Also need to clear _branch_indexes in _invalidate_tracker_read_caches.
---

author: oompah
created: 2026-06-10 01:57
---
Implementation complete: (1) Added work_branch:str|None field to Issue model in models.py; (2) Updated _gh_issue_to_issue in github_tracker.py to read work_branch from body metadata; (3) Added oompah.work_branch to known metadata fields in tracker.py; (4) Added _branch_indexes per-project dict and _build_branch_index() method to Orchestrator; (5) Updated _resolve_task_for_branch to accept project_id and check branch index before legacy fallback; (6) Updated _clear_merge_conflict_label_for_branch to use _resolve_task_for_branch; (7) Updated _invalidate_tracker_read_caches to clear branch indexes; (8) Updated all 3 callers to pass project_id. 17 new tests added (10 in test_yolo_handlers.py, 7 in test_merge_queue.py).
---
<!-- COMMENTS:END -->
