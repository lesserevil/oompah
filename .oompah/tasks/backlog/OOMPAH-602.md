---
id: OOMPAH-602
type: bug
status: Backlog
priority: 1
title: Repair project scope propagation in merged-label maintenance
parent: OOMPAH-588
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:16:01.749200Z'
updated_at: '2026-07-30T14:16:01.749200Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Fix merged-label maintenance so every managed issue operation uses the owning project/tracker scope, including legacy records such as OOMPAH-476 whose issue object lacks project_id. Resolve scope from the managed project iteration or canonical ownership index; never fall back to an unscoped legacy tracker. Persist/backfill safe scope metadata only through supported tracker APIs where necessary, and expose a clear conflict if ownership is ambiguous. Relevant files include merged-label reconciliation, project/tracker routing, issue normalization, and maintenance status.

Tests

Cover missing project_id with known project iteration, ambiguous identifiers across projects, explicit project mismatch, GitHub/native tracker routing, restart, idempotent labels, and no unscoped calls. Run focused maintenance tests and make test.

Acceptance criteria

The merged_labels maintenance lane completes with last_error null; OOMPAH-476 is handled in proj-14849f1b; no task in another project can be mutated through identifier collision.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

