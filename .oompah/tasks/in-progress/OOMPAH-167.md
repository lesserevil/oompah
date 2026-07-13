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
updated_at: '2026-07-13T02:25:36.149703Z'
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
author: oompah
created: 2026-07-13 02:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 02:25
---
UNDERSTANDING: No duplicate found. OOMPAH-167 is a unique child of epic OOMPAH-166 (Standardize epic workflow on shared strategy). OOMPAH-168 (orchestration), OOMPAH-169 (UI), and OOMPAH-170 (docs) are siblings covering other layers, with OOMPAH-168 and OOMPAH-169 blocked on this task.

Scope of OOMPAH-167: domain model, project persistence, project-definition API, and configuration validation. Plan:
1. Find EpicStrategy enum / epic_strategy field in domain model and project persistence
2. Remove flat/stacked variants, keep only shared
3. Add load migration that normalizes persisted flat/stacked -> shared
4. Remove stale enum/options/default handling from validation and API
5. Add unit and API tests: legacy records, new project creation, update validation, serialization, restart-safe migration
6. Run make test to verify
---
<!-- COMMENTS:END -->
