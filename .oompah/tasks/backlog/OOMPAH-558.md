---
id: OOMPAH-558
type: feature
status: Backlog
priority: 0
title: Rebase, test, fast-forward, and audit queued task results
parent: OOMPAH-555
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:24.105345Z'
updated_at: '2026-07-29T16:24:29.334177Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Build the integration executor. Under one epic lease, fetch remote refs, rebase the private task branch onto the expected epic head, run the project configured quality gate on the combined tree, verify the remote head has not changed, fast-forward the epic branch, persist integration evidence, publish coordination events, and request the independent Done audit. Use noninteractive git operations and preserve every recoverable branch on failure.

Tests must cover clean integration, semantic test failure, textual conflict, remote compare-and-swap race, stale or missing task head, audit rejection, retry idempotency, pushed ancestry, and one final epic PR only after all children pass.

Acceptance criteria: only tested combined code reaches the epic branch and Done audit, no concurrent push can overwrite work, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:24
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
<!-- COMMENTS:END -->
