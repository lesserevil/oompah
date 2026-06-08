---
id: TASK-450
title: Detect invalid zero-byte Backlog task files during managed checkout self-heal
status: In Progress
assignee: []
created_date: '2026-06-08 00:09'
updated_date: '2026-06-08 00:36'
labels:
  - bug
dependencies: []
priority: high
ordinal: 86000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Managed checkout self-heal currently treats a repo as sound when it has no unmerged paths, no conflict markers, is on the default branch, and is fast-forwarded. After a disk-full event, managed trickle and oompah checkouts contained zero-byte Backlog task files with missing YAML frontmatter. sync_project_sources still reported git=ok backlog=ok conflicts=none, while Backlog parsed them as invalid or blank tasks. Expected behavior: managed checkout self-heal should validate Backlog task markdown files for required frontmatter, detect zero-byte or malformed task files, and either recover them from a safe source such as the matching task branch/origin/default state or quarantine the project with a dashboard alert instead of reporting sound. Add regression tests for zero-byte tracked task files, zero-byte untracked recovery tasks, and malformed frontmatter files.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Confirmed not a duplicate. TASK-431 handles Git conflict markers; TASK-450 handles zero-byte and missing-frontmatter files caused by disk-full events. The _sound() check in ensure_repo_sound() (backlog_conflict.py:846) does not check for zero-byte or malformed task files. Implementation plan: (1) Add detect_invalid_backlog_task_files() to backlog_conflict.py, (2) Add recovery from origin for zero-byte tracked files, (3) Update ensure_repo_sound/_sound to include the new check, (4) Add regression tests.

Discovery: TASK-431 implemented conflict-marker detection/repair but _sound() in ensure_repo_sound() (backlog_conflict.py) did not check for zero-byte or missing-frontmatter files. These slipped through all existing checks since git sees them as normal modified files with no markers or unmerged index entries.

Implementation: Added inspect_repo_invalid_backlog_task_files() and recover_invalid_backlog_task_files() to oompah/backlog_conflict.py. Integrated recovery as step 5b in ensure_repo_sound(). Updated _sound() to include check. Updated unrecoverable list in steps 8/9 to include invalid files. Added 20 regression tests covering: zero-byte tracked detection, malformed frontmatter detection, conflict-marker exclusion, completed subdir detection, recovery from HEAD, recovery from origin, spurious untracked removal, unrecoverable tracked files, ensure_repo_sound integration, and sync_project_sources quarantine. All 89 tests pass.
<!-- SECTION:NOTES:END -->
