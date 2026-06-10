---
id: TASK-461.6
title: Update watchers and auto-filed task creation for GitHub
status: Done
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-10 08:04'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-460.3
  - TASK-461.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/error_watcher.py
  - oompah/orchestrator.py
  - tests/test_error_watcher.py
parent_task_id: TASK-461
priority: high
ordinal: 142000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update ErrorWatcher, AgentWatcher, duplicate detection, CI-fix sibling filing, release-pick child task creation hooks, and other create_issue callers so new auto-filed work goes to GitHub Issues by default.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Auto-filed tasks include tracker identity, source project, and dedup metadata.
- [ ] #2 Existing source-task comments still go to the source task backend.
<!-- AC:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-10 05:27

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-10 05:27

Focus: CI Failure Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-10 05:46

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Updated ErrorWatcher auto-filed task metadata for GitHub migration readiness. ErrorWatcher-created tasks now include source_project, compact tracker label, structured tracker_kind/tracker_owner/tracker_repo where available, source_issue when provided, and dedup fingerprint metadata in the filed task body. Added regression tests for Backlog and GitHub tracker identity metadata, source issue metadata, dedup metadata, and auto-close comment routing through the bead's own tracker backend. Verified broader create_issue paths already route through project-scoped trackers for release-pick, rebase, watchdog, CI-fix, decomposition, and server-created follow-up tasks. Also updated Backlog-only orchestrator test fixtures and project-lock mocks to match current tracker/worktree helper contracts so the full suite remains green.
<!-- SECTION:FINAL_SUMMARY:END -->
