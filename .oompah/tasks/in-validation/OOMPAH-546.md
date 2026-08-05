---
id: OOMPAH-546
type: feature
status: In Validation
priority: 0
title: Add Ready to Integrate lifecycle and integration metadata
parent: OOMPAH-545
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:08.114469Z'
updated_at: '2026-08-05T19:24:17.551154Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f25e7a0cb9cd
    project_id: proj-14849f1b
    task_id: OOMPAH-546
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: da1be0232d1ddfe4d875ae9bde769f55d3f8145c97b6d70d7406286519e417c0
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T19:24:09.635285+00:00'
  attempt_history: []
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
author: oompah
created: 2026-07-29 18:15
---
The parent epic OOMPAH-545 merged from epic-OOMPAH-545, but this task was Open with work branch unset. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-29 18:17
---
The parent epic OOMPAH-545 merged from epic-OOMPAH-545, but this task was Needs Human with work branch unset. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-29 18:27
---
Implemented in PR #579 and merged to main at 31f8938b8f669a316a830690aaedcc1e0d3834bf. Full GitHub CI passed on Python 3.11, 3.12, and 3.13; focused post-rebase compatibility tests passed.
---
author: oompah
created: 2026-08-05 19:24
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
