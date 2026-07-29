---
id: OOMPAH-543
type: bug
status: In Progress
priority: 1
title: Support removing task dependencies through the CLI and API
parent: null
children: []
blocked_by: []
labels:
- human-only
- needs:backend
- needs:cli
- needs:test
assignee: null
created_at: '2026-07-29T14:38:32.101999Z'
updated_at: '2026-07-29T14:38:42.614821Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Add a supported tracker-neutral removal operation so operators can correct unnecessary dependency edges without hand-editing native task Markdown. Add `oompah task remove-dependency <task-id> --depends-on <blocker-id>`, an authenticated server endpoint, TrackerProtocol support, and native oompah Markdown tracker persistence through the state branch. The operation must be idempotent when the edge is already absent, reject unresolved task identifiers consistently with add-dependency, invalidate issue caches, broadcast the updated graph, and wake dispatch when removing an edge makes Open work eligible. Update AGENTS/bootstrap CLI quick-reference generation where set-dependency is listed.

Tests

Cover CLI request construction and errors; API auth, validation, project resolution, cache/broadcast/refresh behavior; native tracker state-branch persistence and idempotency; and no mutation of unrelated dependencies. Run focused tests and `make test`.

Acceptance criteria

An operator can remove one exact dependency edge using only the supported oompah CLI; the canonical state-branch task is updated safely; repeated removal is harmless; unrelated edges remain; and newly unblocked Open work is considered immediately.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 14:38
---
Claimed by the interactive Codex session performing the owner-requested Open dependency audit. The human-only label prevents scheduler dispatch while I add the supported removal path and use it to prune verified unnecessary edges.
---
<!-- COMMENTS:END -->
