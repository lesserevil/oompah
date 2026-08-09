---
id: OOMPAH-956
type: bug
status: Backlog
priority: 1
title: Do not consume workflow failure attempts for administrative deferrals
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T11:50:18.472017Z'
updated_at: '2026-08-09T11:50:18.472017Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live production evidence on 2026-08-09: OOMPAH-947 and OOMPAH-949 each consumed four of five durable workflow attempts solely across administrative quiesce/restart windows, with last_error reporting that the durable workflow project was paused or quiesced, leaving only one attempt for substantive work. No active task covers general workflow effects; terminal-auditor-specific historical tasks do not address this path. Scope: classify pre-effect administrative pause, quiesce, lifecycle drain, and equivalent resource deferrals as non-substantive retry/checkpoint events that do not consume the handler failure budget. Preserve immutable history and observability, exact job generation/lease fencing, exponential retry scheduling, fail-closed treatment of uncertain post-effect outcomes, and real handler failure exhaustion. Required tests: more than max_attempts pause/quiesce/restart cycles leave the exact job claimable and preserve its checkpoint; genuine pre/post-effect handler failures increment and exhaust as designed; uncertain effect commit remains fail-closed; ABA/replacement generations are unaffected; resume posts bounded continuation and naturally executes work. Acceptance: lifecycle administration cannot strand valid work by spending its substantive retry budget, while genuine failures still converge to exhausted according to policy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

