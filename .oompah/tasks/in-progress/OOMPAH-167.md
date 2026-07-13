---
id: OOMPAH-167
type: task
status: In Progress
priority: 1
title: Remove flat and stacked strategy configuration
parent: OOMPAH-166
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T02:23:05.076076Z'
updated_at: '2026-07-13T02:24:34.640894Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 2d48cbf6-6471-4a32-b832-5d1609a6fb1b
---
## Summary

Make shared the only supported epic strategy in the domain model, project persistence, project-definition API, and configuration validation. Remove the ability to set flat or stacked. Add a backward-compatible load migration that normalizes existing persisted flat/stacked values to shared and writes the normalized project definition on the next safe save. Remove stale enum/options/default handling. Add unit and API tests for legacy records, new project creation, update validation, serialization, and restart-safe migration.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 02:24
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
