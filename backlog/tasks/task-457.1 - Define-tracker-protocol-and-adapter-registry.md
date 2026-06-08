---
id: TASK-457.1
title: Define tracker protocol and adapter registry
status: Backlog
assignee: []
created_date: '2026-06-08 17:56'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies: []
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/tracker.py
  - oompah/orchestrator.py
  - oompah/config.py
parent_task_id: TASK-457
priority: high
ordinal: 109000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Introduce a typed tracker protocol or abstract base for all operations used by server, orchestrator, watchers, prompts, and attachments. Add an adapter registry so tracker.kind resolves to a concrete factory instead of hard-coded BacklogMdTracker construction.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Protocol includes issue fetch/create/update/comment/label/dependency/metadata/cache operations used by oompah.
- [ ] #2 Unknown tracker.kind values still fail validation with clear errors.
<!-- AC:END -->
