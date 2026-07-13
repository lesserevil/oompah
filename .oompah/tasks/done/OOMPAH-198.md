---
id: OOMPAH-198
type: task
status: Done
priority: 2
title: Expose the read-only release delivery inventory API
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-197
labels: []
assignee: null
created_at: '2026-07-13T19:32:50.653200Z'
updated_at: '2026-07-13T22:16:47.491336Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f3ff67dc-9d33-40b9-9241-4fa6e8b8d140
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md section 4.2 GET contract.

Add the project-scoped release-delivery commits endpoint around CommitInventoryService. Validate project, supported release-line selection, filter/query/cursor/limit parameters, and return the documented source snapshot, branch metadata, rows, evidence, next cursor, stale flag, and refresh timestamp. Keep Git work off the async event loop.

Acceptance criteria
- GET /api/v1/projects/{project_id}/release-delivery/commits implements the documented response shape.
- Invalid project/branch/query/limit values receive clear 4xx responses; Git/tracker failures receive actionable 503 responses.
- Cross-project rows never appear, and source SHA/PR links are returned only when safely known.
- Cache invalidation is wired to default/release push webhooks and delivery lifecycle updates.

Tests
- Server tests cover happy path, branch filtering, needs_delivery, all commits, search, pagination, stale cursor, stale fallback, project isolation, and error responses.
- Tests assert Git service calls occur through asyncio.to_thread.

Dependencies
- OOMPAH-197.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 22:05
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 22:05
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 22:06
---
Duplicate investigation complete: OOMPAH-198 is unique. No other task implements the GET /api/v1/projects/{project_id}/release-delivery/commits read-only inventory endpoint. OOMPAH-197 covers the CommitInventoryService itself; OOMPAH-199 covers the POST write endpoint; no archived task covers this GET contract.

Proceeding with implementation. Plan: wrap CommitInventoryService (from OOMPAH-197) in a FastAPI/aiohttp route that validates project, release branch selection, filter/query/cursor/limit params, runs Git work via asyncio.to_thread, and returns the documented response shape from plans/release-delivery-commit-inventory.md section 4.2. Cache invalidation wired to push webhooks and delivery lifecycle updates. Tests will cover all required scenarios (happy path, branch filtering, needs_delivery, all commits, search, pagination, stale cursor, stale fallback, project isolation, error responses, and asyncio.to_thread assertion).
---
author: oompah
created: 2026-07-13 22:09
---
Discovery: CommitInventoryService (OOMPAH-197) is already fully implemented in oompah/release_delivery_inventory.py. The server.py has no GET /api/v1/projects/{project_id}/release-delivery/commits route yet — that's what this task needs.

Key code locations:
- oompah/release_delivery_inventory.py: CommitInventoryService, InventoryPage, SourceChangedError, InventoryError
- oompah/server.py ~line 3380: insert point after release-branch catalog endpoint
- oompah/server.py ~line 9623: webhook push handler where invalidate_release_branch_catalog is called — also wire invalidate_commit_inventory here
- oompah/server.py ~line 4157: _invalidate_addendum_caches — wire invalidate_commit_inventory here for delivery lifecycle updates

Plan: (1) Add _commit_inventory_services registry + _get_commit_inventory_service helper, (2) Add invalidate_commit_inventory function, (3) Add GET endpoint with param validation, asyncio.to_thread, full response serialization, (4) Wire cache invalidation into webhook/lifecycle paths, (5) Write tests/test_server_release_delivery_commits.py.
---
author: oompah
created: 2026-07-13 22:15
---
Implementation complete. Changes made:

1. oompah/server.py:
   - Added _commit_inventory_services dict registry (keyed by project_id) and _commit_inventory_services_lock for thread safety.
   - Added _get_commit_inventory_service(project) helper: lazily creates and caches a CommitInventoryService per project, using make_delivery_store for read-only ledger access.
   - Added invalidate_commit_inventory(project_id) function: finds and calls svc.invalidate(project_id) on the cached service, or no-ops if not yet instantiated.
   - Added GET /api/v1/projects/{project_id}/release-delivery/commits endpoint:
     * Validates project exists (404) and has repo_path (503).
     * Validates branches against supported_release_branches (400), filter (400), limit (400 if not int or <1).
     * Calls service.get_page() via asyncio.to_thread — never blocks event loop.
     * Returns 409 on SourceChangedError with cursor_head/current_head, 400 on malformed cursor, 503 on InventoryError.
     * Serializes InventoryPage to documented JSON shape: project_id, source_branch, source_head, release_branches, rows (with sha, short_sha, subject, author_name, authored_at, parents, selectable, association, release_status cells), next_cursor, stale, refreshed_at.
     * Cells include evidence/delivery_id/pr_url/result_commits only when non-None/non-empty.
   - Wired invalidate_commit_inventory into _invalidate_addendum_caches (delivery lifecycle updates: retry, archive, approve).
   - Wired invalidate_commit_inventory into push webhook handler (alongside existing invalidate_release_branch_catalog call).

2. tests/test_server_release_delivery_commits.py (new, 49 tests):
   - TestHappyPath: 200, all documented fields present, release_status cells, association, pagination fields.
   - TestBranchFiltering: branches param, multiple branches, default=all configured.
   - TestFilterParam: needs_delivery, all, default=needs_delivery.
   - TestSearchParam: query passed to service, empty → None.
   - TestPagination: cursor/limit forwarding, default limit=100, next_cursor echoed.
   - TestStaleCursor: 409 with source_changed code, cursor_head/current_head fields.
   - TestStaleFallback: stale=true forwarded, stale branch info forwarded.
   - TestProjectIsolation: separate services per project, same project → same service, response scoped to project_id.
   - TestErrorResponses: 404 no project, 400 invalid branch/filter/limit/cursor, 503 no_repo/inventory_unavailable.
   - TestAsyncioToThread: verifies asyncio.to_thread is called with service.get_page.
   - TestCacheInvalidation: invalidate wires to service, noop for unknown project, _invalidate_addendum_caches calls it, push webhook path.
   - TestRowStructure: all required row fields present, parents is list, delivered cell evidence fields, null association for direct commits.
   - TestBranchAvailability: unavailable branch rendered with available=False, head=None.
---
author: oompah
created: 2026-07-13 22:15
---
Verification: make test passed — 8487 passed, 28 skipped, 0 failures. All 49 new tests in test_server_release_delivery_commits.py pass. Full regression suite clean.
---
author: oompah
created: 2026-07-13 22:16
---
Completion: Delivered GET /api/v1/projects/{project_id}/release-delivery/commits.

Key deliverables:
- Endpoint wraps CommitInventoryService (OOMPAH-197) with full parameter validation and documented JSON response shape.
- All Git work runs via asyncio.to_thread — event loop never blocked.
- 404 (project not found), 400 (invalid branch/filter/limit/cursor), 409 (stale cursor/source_changed), 503 (no repo_path or InventoryError) error responses with structured error objects.
- Per-project service registry with lazy creation and thread-safe access.
- Cache invalidation wired to push webhooks and delivery lifecycle updates (_invalidate_addendum_caches → retry, archive, approve).
- 49 tests in tests/test_server_release_delivery_commits.py covering all acceptance criteria.
- Full test suite: 8487 passed, 28 skipped, 0 failures.
- Branch epic-OOMPAH-192 pushed to origin.
---
author: oompah
created: 2026-07-13 22:16
---
Implemented GET /api/v1/projects/{project_id}/release-delivery/commits with full param validation, asyncio.to_thread, documented response shape, 404/400/409/503 error handling, per-project service registry, cache invalidation wired to push webhooks and delivery lifecycle updates. 49 new tests; full suite 8487 passed.
---
author: oompah
created: 2026-07-13 22:16
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 79
- Tokens: 118 in / 3.3K out [3.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 11m 43s
- Log: OOMPAH-198__20260713T220511Z.jsonl
---
<!-- COMMENTS:END -->
