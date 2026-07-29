---
id: OOMPAH-541
type: bug
status: Backlog
priority: 1
title: Use resolved project identity in duplicate-screening task details
parent: null
children: []
blocked_by: []
labels:
- human-only
- needs:backend
- needs:test
assignee: null
created_at: '2026-07-29T01:23:36.484044Z'
updated_at: '2026-07-29T01:23:36.484044Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-540

Production verification after OOMPAH-540 exposed a task-detail-only fingerprint bug. GET /api/v1/issues/OOMPAH-472/detail resolves project_id=proj-14849f1b and returns that ID in the response, but calls _issue_duplicate_screening_summary on the tracker Issue before assigning the resolved project ID. Native Markdown tracker issues do not carry project_id, while duplicate fingerprints include it, so the detail endpoint falsely reports a current no_duplicate record as stale. The board path first assigns project_id and correctly reports checked.\n\nImplementation scope:\n- Ensure the detail endpoint assesses duplicate screening with the resolved project identity without mutating persisted task content.\n- Preserve cross-project lookup behavior and all fingerprint semantics.\n- Add a regression test where a native tracker issue has no project_id, its stored screening record was created with the managed project ID, and the detail response reports checked/required rather than stale.\n- Verify the board and detail representations agree.\n\nAcceptance criteria:\nFor a current stored duplicate-screening record, GET issue detail returns state=checked when project_id is supplied or resolved; material task changes still return stale; cross-project issue resolution remains correct; focused API tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

