---
id: OOMPAH-196
type: task
status: In Progress
priority: 1
title: Provide task and epic release-addendum compatibility over the ledger
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-194
- OOMPAH-195
labels: []
assignee: null
created_at: '2026-07-13T19:32:14.875922Z'
updated_at: '2026-07-13T21:02:32.026521Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 48862d7f-f0ea-4316-9d01-44e9b24579e6
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md sections 3.2 and 4.2.

Adapt existing task/epic release-addendum read, approval, retry, and archive paths to use the new project ledger while preserving the documented task-detail API request shapes during the compatibility window. Task and epic views query deliveries by source_identifier; task/epic approval resolves the existing immutable source-commit snapshot and creates ledger entries, never new task metadata addendums.

Acceptance criteria
- Existing task and epic detail screens show historical and new deliveries after migration.
- Approval from a Merged task/epic persists ledger deliveries and wakes the queue.
- Retry/archive only change the selected ledger delivery and enforce valid transitions.
- New approvals do not write oompah.release_addendums metadata or create child backport tasks.

Tests
- Server tests cover task and epic reads/approvals before and after migration, idempotent approval, invalid transitions, and source-commit resolution failures.
- Regression tests prove no legacy metadata entry or child task is created.

Dependencies
- OOMPAH-194 and OOMPAH-195.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 20:55
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 20:56
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 20:56
---
Duplicate investigation complete: no duplicate found. OOMPAH-196 is distinct from all siblings. OOMPAH-193 built the ledger store, OOMPAH-194 built the migration and DualReadDeliveryAdapter, OOMPAH-195 is refactoring the queue/executor. OOMPAH-196 specifically covers: (1) task/epic detail reads querying ledger by source_identifier, (2) task/epic approval (POST /api/v1/issues/{id}/release-addendums) writing ledger deliveries instead of task metadata, (3) retry/archive operating on ledger delivery_id, (4) no new oompah.release_addendums metadata written on approval. Proceeding with implementation.
---
author: oompah
created: 2026-07-13 21:02
---
Discovery: Found all relevant code. The 4 endpoints to adapt:
1. GET /api/v1/issues/{id}/release-addendums (server.py:3962) - reads via AddendumRepository, must switch to DualReadDeliveryAdapter (from OOMPAH-194)
2. POST /api/v1/issues/{id}/release-addendums (server.py:3644) - calls approve_release_addendums() which writes oompah.release_addendums task metadata; must write ledger ReleaseDelivery records instead
3. POST .../retry (server.py:4072) - loads AddendumRepository, transitions; must look in ledger first by delivery_id
4. POST .../archive (server.py:4251) - same

Plan: create oompah/release_delivery_compat.py with delivery_to_compat_raw(), make_delivery_store(), make_delivery_adapter(), and approve_release_addendums_via_ledger(). Modify server.py endpoints to use the new module. Add tests in tests/test_server_release_addendums_ledger.py.
---
<!-- COMMENTS:END -->
