---
id: OOMPAH-795
type: feature
status: Backlog
priority: 1
title: Expose one why-not-progressing projection and make alerts truthful
parent: OOMPAH-770
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:59:25.042939Z'
updated_at: '2026-08-04T13:59:25.042939Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Make API, dashboard board/detail, queue rows, agent panels, and alerts consume WorkDecision rather than local heuristics. Expose owner, disposition, reason code/text, prerequisites, evidence revision, next reassessment, recovery action, and action_required. Global warnings must contain only operator-actionable conditions; queued work, active repair, retry backoff, audit rotation, CI pending, and capacity waits remain task-local/informational. Preserve WebSocket sequence/full-sync behavior and secret redaction. Required tests: executor/UI parity, alert severity transitions and clearing, stale snapshot resync, compact dashboard rendering, accessibility, auth/redaction, and no warning for normal recovery. Acceptance: operator can answer why any task is idle from one projection and every global warning requires an actual operator action.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

