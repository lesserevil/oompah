---
id: OOMPAH-871
type: bug
status: Backlog
priority: 1
title: Prevent provenance-only terminal tasks from watchdog reopen and redispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T05:24:14.554398Z'
updated_at: '2026-08-07T05:24:14.554398Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-576

Reproduce OOMPAH-576 after its original implementation merged and an operator explicitly retained the record only as terminal provenance. A watchdog later reopened and redispatched the task, causing a new documentation-only accepted head and another full validation/review cycle. Define and persist an authoritative provenance-only or terminal-suppression state that every watchdog, reconciliation path, dependency rollup, and restart recovery honors. Relevant code: watchdog task reconciliation, terminal-state evidence, archived/provenance metadata, dispatch eligibility, restart recovery. Required tests: terminal provenance records remain non-dispatchable across repeated watchdog ticks and service restart; legitimate owner-requested revision creates a new authority generation and can dispatch; stale branch or historical review observations cannot reopen the record; alerts explain malformed provenance metadata without mutating status. Acceptance: a task retained solely as merged/archived provenance cannot re-enter a dispatchable or validation state unless a project owner explicitly starts a new revision.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

