---
id: OOMPAH-414
type: task
status: Backlog
priority: null
title: Prevent scheduler stalls from delaying task dispatch
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T19:20:53.199562Z'
updated_at: '2026-07-23T19:20:53.199562Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Investigate and fix the event-driven scheduler stall observed on 2026-07-23: after the Exocomp task push, the last completed tick and state snapshot remained at 19:15 UTC with no running agents and no new dispatch. The current stale-loop recovery threshold is full_sync_interval × factor (15 minutes), delaying recovery. Identify the blocking tick phase from diagnostics, ensure maintenance work cannot starve the dispatch loop, and make stale-dispatch recovery prompt and observable. Add regression coverage for the observed stall/recovery path and run make test. Acceptance: a stalled scheduler recovers before newly opened work is delayed for the current 15-minute threshold; clean eligible Exocomp tasks dispatch after recovery.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

