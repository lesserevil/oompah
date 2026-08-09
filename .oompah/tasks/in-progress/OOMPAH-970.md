---
id: OOMPAH-970
type: task
status: In Progress
priority: null
title: Make detached workflow heartbeat proof deterministic under loaded CI
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T19:37:32.521266Z'
updated_at: '2026-08-09T19:41:20.671923Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Hosted PR #776 exact head 6f3ee4170 reproduced a timing race in Python 3.12 after 19,176 tests passed: tests/test_workflow_runtime.py::test_detached_effect_heartbeats_and_drains_without_duplicate_apply sleeps 220ms against a 150ms real-time lease and then requires lease_expires_at > time.time(); under loaded CI the most recent heartbeat missed that narrow observation by about 63ms. Python 3.11/3.13 passed and the failure is unrelated to the OOMPAH-968 production diff, but a race-dependent test is a bug.\n\nImplementation scope: replace wall-clock sleep/hope with a deterministic synchronization or injectable clock/renewal observation that proves the actual detached worker heartbeat renews the exact job lease while apply remains blocked; then prove drain does not duplicate the effect and completion occurs once. Do not weaken lease-expiry production behavior or merely widen sleeps/timeouts. Relevant files: tests/test_workflow_runtime.py and narrow WorkflowRuntime/DurableWorkflowWorker test seams only if necessary. Search and preserve OOMPAH-957 deterministic timing conventions.\n\nRequired tests: the heartbeat proof passes repeatedly under loaded scheduling without wall-clock races; it still fails if the heartbeat does not renew; exact lease ownership, drain false-while-blocked, single apply, and final completion remain asserted. Acceptance: repeated focused runs pass, workflow runtime module passes, Ruff/diff checks pass, and protected Python 3.11/3.12/3.13 CI passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 19:37
---
Accepted for direct-owner repair from PR #776 Python 3.12. The protected job is rerunning; this task removes the underlying sleep-based race regardless of retry outcome.
---
<!-- COMMENTS:END -->
