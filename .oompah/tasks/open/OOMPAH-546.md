---
id: OOMPAH-546
type: feature
status: Open
priority: 0
title: Add Ready to Integrate lifecycle and integration metadata
parent: OOMPAH-545
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:08.114469Z'
updated_at: '2026-07-29T17:57:08.161082Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement the canonical nonterminal Ready to Integrate status and a versioned oompah.integration metadata record containing task branch, base/head/integrated SHAs, queue state, attempts, timestamps, and last error. Update canonical status aliases, dispatch/review/rollup sets, native Markdown/GitHub/GitLab normalization and metadata persistence, state/task APIs, labels, and dashboard columns. Ready tasks must not dispatch or be treated as orphaned In Progress work.

Tests must cover canonicalization, tracker round trips, epic rollup, board/detail responses, watchdog behavior, label bootstrap, and backward compatibility for tasks without metadata.

Acceptance criteria: the status and metadata survive every tracker adapter and restart, are visible in APIs/UI, do not trigger workers, and all focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:23
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
author: oompah
created: 2026-07-29 16:25
---
Interactive owner session started implementation on the lifecycle and metadata foundation.
---
author: oompah
created: 2026-07-29 17:57
---
Implementation is complete on epic-OOMPAH-545. Full project gate passed: 13,213 tests passed, 7 skipped. Final rebase, merge, and deployment are in progress; this task remains human-owned and must not be dispatched.
---
<!-- COMMENTS:END -->
