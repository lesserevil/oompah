---
id: TASK-172
title: _resolve_capabilities helper in orchestrator
status: Done
assignee: []
created_date: 2026-04-28 20:56
updated_date: 2026-04-29 02:23
labels:
- beads-migrated
dependencies:
- TASK-171
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-zlz.3
  state: closed
  parent_id: oompah-zlz
  dependencies:
  - oompah-zlz.2
  branch_name: oompah-zlz.3
  target_branch: null
  url: null
  created_at: '2026-04-28T20:56:35Z'
  updated_at: '2026-04-29T02:23:38Z'
  closed_at: '2026-04-29T02:23:38Z'
parent: TASK-165
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add _resolve_capabilities(provider, model) returning the modality list for a resolved model, defaulting to ['text']. Used by the prompt renderer and api_agent wiring to decide whether to send attachments. Tests cover declared, missing, and wildcard mappings.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019dd6e3-0efe-79c0-9a63-e9d9eab979a4
author: oompah
created: 2026-04-29T01:38:18Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e3-1af6-72d6-9463-0a2c5c99b941
author: oompah
created: 2026-04-29T01:38:21Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
