---
id: TASK-450
title: Detect invalid zero-byte Backlog task files during managed checkout self-heal
status: Backlog
assignee: []
created_date: '2026-06-08 00:09'
updated_date: '2026-06-08 00:09'
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
