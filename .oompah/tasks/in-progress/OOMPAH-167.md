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
updated_at: '2026-07-13T02:32:09.682372Z'
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
author: oompah
created: 2026-07-13 02:26
---
DISCOVERY: Found all relevant code. Changes needed across 3 files:

**oompah/models.py (Project class)**:
- Field default: epic_strategy='stacked' → 'shared'
- from_dict(): fallback 'flat' → 'shared'; add migration: flat/stacked → shared; remove old validation that falls back to 'flat' for unknown values
- to_dict(): update comment about default

**oompah/projects.py (ProjectStore.update)**:
- UPDATABLE_FIELDS: remove 'epic_strategy' (or keep but only allow 'shared')
- update() validation: reject flat/stacked, only allow 'shared', or remove the field from update API entirely; if None → 'shared' (not 'flat')

**oompah/server.py (PATCH /api/v1/projects/{id})**:
- epic_strategy handler: reject flat/stacked, only accept 'shared', or reject any attempt to set it

**oompah/orchestrator.py (_project_epic_strategy)**:
- Fallback 'flat' → 'shared'; remove flat/stacked from valid strategy list (but this is OOMPAH-168's scope - will just update the config layer here)

**tests/test_epic_strategy.py**: Extensive existing tests that will need updating (test_default_is_stacked → shared, back-compat flat → shared migration, invalid → shared not flat, update validation)

Strategy: Remove epic_strategy from UPDATABLE_FIELDS (can no longer be changed once the field is removed from the API), OR keep it in UPDATABLE_FIELDS but change the validation to only accept 'shared'. Decision: Keep in UPDATABLE_FIELDS but reject flat/stacked (so clients can still set it to 'shared' explicitly). The key behavior changes are the migration and the default.
---
author: oompah
created: 2026-07-13 02:32
---
IMPLEMENTATION: Made the following changes across 3 files to make 'shared' the only supported epic strategy:

**oompah/models.py**:
- Changed epic_strategy default: 'stacked' → 'shared'
- Updated field docstring to reflect shared-only
- from_dict(): all persisted values (flat, stacked, unknown) normalize to 'shared' at load time — restart-safe migration
- to_dict(): updated comment to reflect shared-only

**oompah/projects.py**:
- ProjectStore.update(): changed validation to only accept 'shared'; flat/stacked now raise ProjectError with clear message; None now defaults to 'shared' (was 'flat')

**oompah/server.py**:
- PATCH /api/v1/projects/{id} epic_strategy handler: only accepts 'shared'; rejects flat/stacked with 400 and descriptive message; None → 'shared'

**tests/test_epic_strategy.py**:
- Updated TestProjectEpicStrategyField: renamed test_default_is_stacked → test_default_is_shared; added migration tests for flat→shared, stacked→shared, unknown→shared, serialization after migration
- Updated TestProjectStoreUpdateEpicStrategy: stacked/flat now expect ProjectError; added test_update_to_flat_is_rejected; updated None behavior (→ shared not flat)

**tests/test_projects_crud.py**:
- Added 7 new API tests in TestProjectAPI covering: accept shared, accept SHARED (case), null→shared, reject flat, reject stacked, reject bogus, new project defaults to shared
---
<!-- COMMENTS:END -->
