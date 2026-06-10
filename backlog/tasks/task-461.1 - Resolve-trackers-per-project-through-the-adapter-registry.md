---
id: TASK-461.1
title: Resolve trackers per project through the adapter registry
status: In Progress
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-10 00:39'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457.5
  - TASK-459.3
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - tests/test_backlog_tracker.py
parent_task_id: TASK-461
priority: high
ordinal: 137000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update orchestrator tracker construction and caching so each project uses its configured tracker backend. Preserve legacy Backlog behavior while allowing GitHub-backed projects to share the central task hub.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Project tracker lookup can return BacklogMdTracker or GitHubIssueTracker.
- [ ] #2 Tracker cache invalidation remains project-scoped where needed.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 00:04
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 00:04
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 00:17
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 00:20
---
Understanding: TASK-461.1 is NOT a duplicate. Previous Duplicate Investigator runs found no matching task. The closest related tasks (TASK-457.1, TASK-459.3) have been merged and are Done - they laid the groundwork (TrackerProtocol, ADAPTER_REGISTRY, per-project tracker fields in Project model). TASK-457.5 (audit BacklogMdTracker assumptions) is still Open but is a separate concern (isolating BacklogMdTracker usage) vs this task (per-project tracker construction in orchestrator). There are uncommitted changes in oompah/orchestrator.py from a previous run: _new_tracker_for_project() method added and _tracker_for_project() updated. Need to: (1) verify the implementation is correct; (2) add tests; (3) run full test suite; (4) commit and push.
---

author: oompah
created: 2026-06-10 00:23
---
Discovery: Found the implementation in oompah/orchestrator.py (uncommitted from previous agent run): _new_tracker_for_project() resolves tracker_kind from project fields (fallback to global config) and passes owner/repo kwargs for GitHub projects. However, _github_issues_factory in oompah/github_tracker.py has **kwargs but ignores owner/repo - it only reads from env vars. This means the per-project owner/repo are silently dropped. Fix needed: update _github_issues_factory to accept owner/repo as named params, preferring them over env vars. Tests are also missing for _new_tracker_for_project and the updated _tracker_for_project.
---

author: oompah
created: 2026-06-10 00:39
---
Implementation: (1) oompah/orchestrator.py - Added _new_tracker_for_project(project) method that resolves tracker_kind from project.tracker_kind (falling back to global config for unconfigured projects), looks up the factory in ADAPTER_REGISTRY, and passes owner/repo kwargs for github_issues projects. Updated _tracker_for_project() to use this new method. Made the tracker_kind resolution defensive: only uses project_kind if it's a non-empty string (handles MagicMock in tests and None correctly). (2) oompah/github_tracker.py - Fixed _github_issues_factory to accept owner/repo as named kwargs with env var fallback, so per-project tracker_owner/tracker_repo from Project model are actually used. (3) tests/test_backlog_tracker.py - Added 15 tests in 3 test classes: TestNewTrackerForProject (6 tests), TestTrackerForProject (5 tests), TestGitHubIssuesFactoryOwnerRepoKwargs (4 tests).
---
<!-- COMMENTS:END -->
