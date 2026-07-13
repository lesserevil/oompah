---
id: OOMPAH-198
type: task
status: In Progress
priority: 2
title: Expose the read-only release delivery inventory API
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-197
labels: []
assignee: null
created_at: '2026-07-13T19:32:50.653200Z'
updated_at: '2026-07-13T22:04:59.912181Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

