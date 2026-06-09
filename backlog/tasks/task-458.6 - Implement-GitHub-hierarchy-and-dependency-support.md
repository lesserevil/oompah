---
id: TASK-458.6
title: Implement GitHub hierarchy and dependency support
status: Done
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-09 13:29'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-458.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/github_tracker.py
  - tests
parent_task_id: TASK-458
priority: high
ordinal: 120000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Support epics, child tasks, and blockers using GitHub sub-issues and issue dependencies where available. Add adapter-level fallback metadata for any GitHub API surface that is unavailable, while preserving the tracker protocol.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 fetch_children and add_dependency work through the protocol.
- [x] #2 Fallback relationship metadata renders the same normalized Issue relationships.
<!-- AC:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-09 07:21

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-09 07:22

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-09 07:46

Agent completed successfully in 1483s (2741174 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-09 07:46

Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 29, Tool calls: 28
- Tokens: 2.7M in / 10.1K out [2.7M total]
- Cost: $0.0000
- Exit: normal, Duration: 24m 43s
- Log: TASK-458.6__20260609T072235Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-09 07:47

Agent completed without closing this issue (1483s (2741174 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-09 07:55

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented GitHub hierarchy and dependency support. GitHub Issues now normalize parent and dependency labels into Issue.parent_id and Issue.blocked_by, filter those internal labels from user-facing labels, use GitHub sub-issues and blocked-by dependency APIs with issue database IDs, and fall back to parent:<number> / depends-on:<number> labels when those APIs are unavailable. Added PyJWT[crypto] as an explicit runtime dependency for GitHub App authentication. Verification: focused hierarchy/dependency tests passed, tracker protocol/backlog/shared contract suites passed, and full make test passed with 5905 passed, 4 skipped.
<!-- SECTION:FINAL_SUMMARY:END -->
