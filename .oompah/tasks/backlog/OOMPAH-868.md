---
id: OOMPAH-868
type: bug
status: Backlog
priority: 1
title: Broker self-hosted CI validation and bound log amplification
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T23:27:55.534862Z'
updated_at: '2026-08-06T23:27:55.534862Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-768

Live reproduction on 2026-08-06: dedicated GitHub Actions run 31129704050 launched a full pytest process on the same host while the Oompah validation-resource database reported no owner or waiter. The run therefore bypasses the capacity-1 broker used by exact gates and managed workers. Its pytest -v command emits more than 16,000 per-test records; the process repeatedly entered jbd2_log_wait_commit and delayed both CI and local focused repair validation. Implementation scope: route every dedicated self-hosted CI full gate through the shared durable validation-resource lease before pytest starts, using a stable project/task/run authority identity and releasing on completion, cancellation, runner death, or timeout; prevent overlap with server exact gates and managed worker or auditor validation; replace per-test verbose console amplification with bounded console output while preserving complete failure diagnostics through a durable artifact or equivalent. Relevant files include .github/workflows/ci-dedicated.yml, validation lease integration scripts, and tests for runner lifecycle and command classification. Required tests: a simulated dedicated run waits while capacity=1 is owned, begins immediately after release, cancellation and owner death free capacity, concurrent runs cannot exceed capacity, and success/failure diagnostics remain available without verbose per-test streaming. Acceptance: process-table evidence proves at most one heavyweight validation tree on this host across dedicated CI and Oompah-managed paths, GitHub check conclusions remain correct, and a full clean run no longer causes sustained filesystem journal wait from console amplification.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

