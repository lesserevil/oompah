---
id: OOMPAH-956
type: bug
status: In Progress
priority: 1
title: Do not consume workflow failure attempts for administrative deferrals
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T11:50:18.472017Z'
updated_at: '2026-08-09T12:07:32.642344Z'
work_branch: OOMPAH-956
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-956
  base_branch: epic-OOMPAH-940
  base_sha: 41a158291ad932b232e9ebc4dcff5b0357d9f57b
  head_sha: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
  submitted_at: '2026-08-09T12:07:19.976703+00:00'
  updated_at: '2026-08-09T12:07:19.976703+00:00'
oompah.work_branch: OOMPAH-956
---
## Summary

Live production evidence on 2026-08-09: OOMPAH-947 and OOMPAH-949 each consumed four of five durable workflow attempts solely across administrative quiesce/restart windows, with last_error reporting that the durable workflow project was paused or quiesced, leaving only one attempt for substantive work. No active task covers general workflow effects; terminal-auditor-specific historical tasks do not address this path. Scope: classify pre-effect administrative pause, quiesce, lifecycle drain, and equivalent resource deferrals as non-substantive retry/checkpoint events that do not consume the handler failure budget. Preserve immutable history and observability, exact job generation/lease fencing, exponential retry scheduling, fail-closed treatment of uncertain post-effect outcomes, and real handler failure exhaustion. Required tests: more than max_attempts pause/quiesce/restart cycles leave the exact job claimable and preserve its checkpoint; genuine pre/post-effect handler failures increment and exhaust as designed; uncertain effect commit remains fail-closed; ABA/replacement generations are unaffected; resume posts bounded continuation and naturally executes work. Acceptance: lifecycle administration cannot strand valid work by spending its substantive retry budget, while genuine failures still converge to exhausted according to policy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 12:07
---
Implemented and pushed 60b94b8844af30c1ff796869eeab3b68b98dbe1f on OOMPAH-956. Proven pre-effect pause/quiesce/lifecycle/resource deferrals now restore claim-time attempts, preserve exact checkpoints/generation, append immutable administrative_deferred events, and retain capped exponential backoff. Genuine failures and uncertain post-effect outcomes still consume/exhaust attempts; exact lease, restart, ABA, and replacement fencing are covered. Verification: 186 focused workflow job/worker/runtime tests passed; 8 new targeted regressions passed; terminal-audit scan and secret scan passed. Additional incident corpus: 43/44 passed, with only the known sibling OOMPAH-748 containment regression on the epic base (fixed independently at dccbeb5).
---
author: oompah
created: 2026-08-09 12:07
---
Pushed 60b94b884: administrative pre-effect deferrals no longer consume workflow failure attempts; exact checkpoint/generation/lease fencing, immutable event history, capped exponential backoff, substantive failure exhaustion, and post-effect fail-closed behavior are regression covered. Focused workflow suites: 186 passed; scans passed.
---
<!-- COMMENTS:END -->
