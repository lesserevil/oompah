---
id: OOMPAH-167
type: task
status: Open
priority: 1
title: Remove flat and stacked strategy configuration
parent: OOMPAH-166
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T02:23:05.076076Z'
updated_at: '2026-07-13T02:24:16.784431Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Make shared the only supported epic strategy in the domain model, project persistence, project-definition API, and configuration validation. Remove the ability to set flat or stacked. Add a backward-compatible load migration that normalizes existing persisted flat/stacked values to shared and writes the normalized project definition on the next safe save. Remove stale enum/options/default handling. Add unit and API tests for legacy records, new project creation, update validation, serialization, and restart-safe migration.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

