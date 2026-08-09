---
id: OOMPAH-961
type: bug
status: Backlog
priority: 1
title: Retire exhausted authority across zero-job and lifecycle handoffs
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T14:20:19.752110Z'
updated_at: '2026-08-09T14:20:19.752110Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Add an atomic durable authority marker for canonical zero-obligation decisions and workflow-domain/lifecycle handoffs so superseded exhausted jobs stop overriding the current decision only after the replacement cut is fully published. Current production evidence shows 12 Done tasks whose newer canonical landing.waiting decision materializes no job, seven managed integration/standalone exhaustions surviving transition to terminal-audit or terminal lifecycle, and three terminal epic_cleanup exhaustions remaining globally current. Do not weaken _CURRENT_EXHAUSTION_PREDICATE based on cursor movement alone. Persist a fail-closed no-job disposition or handoff tombstone in the same authority transaction, teach current-exhaustion and WorkDecisionController invariants to honor only that proof, and retain ambiguous/partial cuts as actionable. Add tests for zero-job blocked/action decisions, managed-to-event terminal-audit handoff, lifecycle-final task and epic retirement, rollback, restart, concurrent publication, ABA generation changes, and cursor-only fail-closed behavior. Acceptance: stale rows no longer produce task alerts or fail rollout health, genuinely current exhausted work remains actionable, and focused tests plus the configured branch gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

