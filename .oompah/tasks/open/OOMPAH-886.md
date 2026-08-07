---
id: OOMPAH-886
type: task
status: Open
priority: null
title: Add atomic idempotent create-once tracker operations
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-879
labels: []
assignee: null
created_at: '2026-08-07T12:42:12.972567Z'
updated_at: '2026-08-07T12:42:25.477813Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

OOMPAH-879 must fail closed after an ambiguous tracker create response because TrackerProtocol.create_issue has no idempotency key: a retry can create a second scheduler helper after the first commit succeeded but its response was lost. Implement a native atomic create-once primitive keyed by project, operation kind, and durable caller-supplied creation marker. Scope: extend the tracker protocol and native Markdown tracker so marker lookup and issue creation commit under the same write/state-branch transaction; an authorized retry returns the exact original issue without another allocation; concurrent requests and restart recovery converge on one issue; adapters that cannot prove create-once support fail closed rather than retry ambiguously. Wire epic-rebase helper creation to reconcile its persisted marker through this primitive, allowing a definitely failed create to retry safely without a permanent reservation deadlock. Relevant context: OOMPAH-879 authority state, tracker protocol/native tracker allocation, state-branch persistence, and helper scheduler. Required tests: response lost after commit then retry; response lost before commit then retry; concurrent same-key calls; same key with mismatched payload rejected; process restart; state-branch push/reconciliation failure; unsupported external tracker; epic-rebase helper resumes naturally and creates exactly one task. Acceptance: no ambiguous create response can duplicate a task or permanently deadlock recoverable creation, and the operation remains fail closed across persistence and adapter failures.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 12:42
---
Filed from OOMPAH-879 final review. OOMPAH-879 ships the immediate no-duplicate fail-closed reservation; this task restores bounded liveness with a real atomic create-once contract after the authority fix lands.
---
<!-- COMMENTS:END -->
