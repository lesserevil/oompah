---
id: OOMPAH-346
type: bug
status: Open
priority: 1
title: Reserve round-robin providers atomically at dispatch time
parent: null
children: []
blocked_by: []
labels:
- provider-selection
- round-robin
assignee: null
created_at: '2026-07-22T00:50:14.701022Z'
updated_at: '2026-07-22T00:50:42.815497Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem
Round-robin provider roles use least-recently-used ordering, but candidate usage is recorded only after a worker session completes. When tasks dispatch concurrently, every dispatch observes the same stale usage state and selects the same provider (currently Claude). Usage is intentionally per role, so a global 50/50 split is not required; each role must be fair among its eligible candidates.

Implement
- Add an atomic dispatch-time reservation/claim operation to CandidateSelector for round-robin roles. It must select the least-recently-used eligible candidate and immediately persist usage/reservation under the selector lock before another dispatch can resolve that role.
- Use the operation in dispatch target resolution/claiming so concurrent tasks cannot all select the same first candidate.
- Preserve provider failover: if the reserved candidate fails preflight or startup, record the attempt and reserve/select the next eligible candidate without corrupting ordering or repeatedly selecting the failed candidate.
- Do not change priority-role behavior or legacy single-provider profile behavior.
- Ensure state persists across service restart and remains safe when concurrent dispatches use the same role.

Tests
- Unit test N concurrent reservations for a two-candidate round-robin role alternate fairly: for even N, counts differ by no more than one, and never exhibit the all-first-candidate race.
- Unit test separate roles retain independent usage state.
- Orchestrator test concurrent dispatches using the same role produce alternating provider targets before workers complete.
- Failover tests for preflight and startup failure, including that the next dispatch gets the correct next candidate.
- Regression test: five concurrent Claude/Codex dispatches include Codex rather than all selecting Claude.

Acceptance criteria
- A simultaneous batch for a Claude/Codex round-robin role is balanced within one dispatch per provider whenever both are eligible.
- Running-task state shows the actual chosen provider.
- No duplicate candidate selection is caused solely by dispatching before a prior session completes.
- Existing provider-selection and full test suites pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

