---
id: OOMPAH-196
type: task
status: Done
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
updated_at: '2026-07-13T21:48:52.645423Z'
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
author: oompah
created: 2026-07-13 21:47
---
Verification: Full test suite passes (8363 passed, 28 skipped, 0 failed). Key fixes applied:

1. release_delivery_compat.py: delivery_to_compat_raw() now accepts optional included_child_ids parameter for epic approval responses
2. server.py GET endpoint: now uses store.lookup_by_source_identifier() + adapter._fetch_legacy_addendums() combo so legacy addendums are served via addendum.to_raw() (preserving included_child_ids) and ledger deliveries via delivery_to_compat_raw()
3. server.py POST endpoint: passes included_child_ids to delivery_to_compat_raw() for newly-created epic deliveries
4. tests/test_server_release_addendums_ledger.py: replaced all asyncio.get_event_loop().run_until_complete() with asyncio.run() to avoid event loop isolation issues across the full test suite
---
author: oompah
created: 2026-07-13 21:48
---
Completion: Delivered ledger-backed task/epic release-addendum compatibility.

Implementation summary:
- oompah/release_delivery_compat.py (new): Core compatibility layer with delivery_to_compat_raw(), approve_release_addendums_via_ledger(), retry_ledger_delivery(), archive_ledger_delivery(), factory helpers, and LedgerApprovalResult
- oompah/server.py (4 endpoints updated): GET uses mixed ledger+legacy with included_child_ids preserved from original addendums; POST creates ledger entries and never writes oompah.release_addendums metadata; retry/archive use ledger-first with legacy shim fallback
- tests/test_server_release_addendums_ledger.py (new, 48 tests): Covers all acceptance criteria including idempotency, epic reads/approvals, source-commit resolution failures, invalid transitions, and regression proofs (no legacy metadata written, no child task creation)
- tests/test_server_release_addendums.py (5 tests updated): Updated for new event/response shapes

All 8363 tests pass. Pushed to epic-OOMPAH-192.
---
<!-- COMMENTS:END -->
