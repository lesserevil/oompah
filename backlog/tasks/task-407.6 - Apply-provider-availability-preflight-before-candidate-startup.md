---
id: TASK-407.6
title: Apply provider availability preflight before candidate startup
status: Backlog
assignee: []
created_date: 2026-06-01 21:44
labels:
- feature
- needs:backend
- needs:test
dependencies:
- TASK-407.5
modified_files:
- oompah/orchestrator.py
- tests/test_orchestrator_handlers.py
parent_task_id: TASK-407
priority: high
ordinal: 36000
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make role candidate failover skip candidates that are known unavailable before starting an agent, using the same normalized provider failure concepts used by the provider test endpoint.

Current state to inspect first:
- Existing dispatch already has budget checks, provider validation, and rate-limit cooldown behavior in several places.
- Some failures are discovered only after starting a worker.
- The new candidate loop from TASK-407.5 needs a clear preflight decision for each candidate.

Required behavior:
- Before starting an agent for a candidate, check whether the provider/model can reasonably be used.
- Skip to the next candidate for missing credentials, invalid model, exhausted paid budget, active provider cooldown, rate limit, overload, and startup timeout.
- Free or subscription-backed candidates must still be allowed when paid token budget is exhausted if current budget rules allow that today.
- If every candidate is skipped or fails preflight, return a clear task retry/error reason listing the candidate reasons.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A paid candidate blocked by budget exhaustion is skipped and the next usable candidate is attempted.
- [ ] #2 A free model candidate is not skipped solely because the paid budget window is exhausted.
- [ ] #3 An ACP subscription candidate is not skipped solely because the paid budget window is exhausted when current billing rules say it is not per-token billed.
- [ ] #4 An active provider cooldown causes the candidate to be skipped.
- [ ] #5 When all candidates are unavailable, the resulting error includes each provider/model and normalized reason.
- [ ] #6 Skip decisions are logged without leaking API keys or secrets.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Inventory current budget, credential, provider validation, and rate-limit checks in orchestrator.py before editing.
2. Create a helper that returns either usable or a normalized skip reason for a DispatchTarget.
3. Reuse the provider test error classification names where practical.
4. Integrate the preflight helper into the candidate loop from TASK-407.5.
5. Preserve existing budget semantics: explicitly free models and non-per-token subscription ACP providers should not be blocked by paid budget exhaustion.
6. Add structured log lines for each skipped candidate with role, provider, model, and reason.
7. Add tests for budget-exhausted paid candidate falling back to free/subscription candidate, active cooldown fallback, missing credentials fallback, and all-candidates-unavailable failure.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests cover provider availability preflight without real network calls.
- [ ] #2 Existing budget tests still pass.
<!-- DOD:END -->
