---
id: OOMPAH-796
type: feature
status: Ready to Integrate
priority: 1
title: Implement the universal totality and liveness controller
parent: OOMPAH-770
children: []
blocked_by:
- OOMPAH-806
- OOMPAH-807
start_blocked_by: &id001
- OOMPAH-785
- OOMPAH-807
labels: []
assignee: null
created_at: '2026-08-04T13:59:26.773150Z'
updated_at: '2026-08-05T20:23:24.632729Z'
work_branch: epic-OOMPAH-770--task-OOMPAH-796
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8bb2e964b0f1cc4d860a880a78e3c62b765dd8cb72b5bcbd2122c63d9151e7af
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T21:25:30.768038+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-770 is the containing epic, while OOMPAH-768,\
    \ OOMPAH-784, OOMPAH-795, and OOMPAH-797 cover migration, metrics, projections,\
    \ and soak qualification respectively. No separate active task duplicates this\
    \ controller implementation.\nFocus handoff: duplicate_detector  \nDuplicate preflight\
    \ verdict: no_duplicate  \nMatches: none  \n\nEvidence: OOMPAH-770 is the containing\
    \ epic, while OOMPAH-768, OOMPAH-784, OOMPAH-795, and OOMPAH-797 cover migration,\
    \ metrics, projections, and soak qualification respectively. No separate active\
    \ task duplicates this controller implementation."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 5e122298-13ee-45f4-a1cd-8ecf6d95f6eb
oompah.work_branch: epic-OOMPAH-770--task-OOMPAH-796
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-770--task-OOMPAH-796
  base_branch: epic-OOMPAH-770
  base_sha: f1e7925b7263f980517f943291102c8c83335ed2
  head_sha: 2af2f103d0375e267de1bcf542d06825bce80d44
  submitted_at: '2026-08-05T20:22:51.265104+00:00'
  updated_at: '2026-08-05T20:23:22.443379+00:00'
oompah.task_costs:
  total_input_tokens: 46798
  total_output_tokens: 39745
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46596
      output_tokens: 599
      cost_usd: 0.0
    sonnet:
      input_tokens: 85
      output_tokens: 2021
      cost_usd: 0.0
    opus:
      input_tokens: 117
      output_tokens: 37125
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 45988
    output_tokens: 418
    cost_usd: 0.0
    recorded_at: '2026-08-04T21:25:30.756760+00:00'
  - profile: default
    model: haiku
    input_tokens: 274
    output_tokens: 81
    cost_usd: 0.0
    recorded_at: '2026-08-04T21:41:57.917530+00:00'
  - profile: default
    model: haiku
    input_tokens: 334
    output_tokens: 100
    cost_usd: 0.0
    recorded_at: '2026-08-05T18:14:23.248101+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 85
    output_tokens: 2021
    cost_usd: 0.0
    recorded_at: '2026-08-05T19:22:11.940904+00:00'
  - profile: deep
    model: opus
    input_tokens: 117
    output_tokens: 37125
    cost_usd: 0.0
    recorded_at: '2026-08-05T20:23:14.464860+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-796__20260804T212503Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-770--task-OOMPAH-796
    source_sha: a681ec2fc005f339063b3b8e2a139b8ae0b3c379
    completed_at: '2026-08-04T21:25:30.786143+00:00'
  - run_id: OOMPAH-796__20260805T192450Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: opus
    focus: oompah_tests
    source_branch: epic-OOMPAH-770--task-OOMPAH-796
    source_sha: 2af2f103d0375e267de1bcf542d06825bce80d44
    completed_at: '2026-08-05T20:23:14.469433+00:00'
---
## Summary

Build a controller that evaluates every nonterminal WorkDecision on relevant events and bounded full-sync. Enforce exactly one disposition: runnable, durably owned, named-prerequisite blocked, retry-scheduled, or action_required. Detect missing/conflicting/expired/impossible ownership, overdue reassessment, exhausted recovery, and graph impossibility. Enqueue reason-coded recovery jobs instead of writing status; deduplicate/escalate only when automatic recovery is unavailable. Required tests: totality across statuses, duplicate owners, missing queue/audit/review job, expired lease, stale facts, retry due/exhausted, dependency cycles, restart convergence, and idempotent remediation. Acceptance: no unknown nonterminal disposition survives one full-sync interval and every synthetic stall recovers or escalates with concrete evidence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:22
---
Hard-start prerequisite OOMPAH-785 is Done. Promoting the universal totality/liveness controller for server dispatch as the first OOMPAH-770 implementation wave.
---
author: oompah
created: 2026-08-04 21:24
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 21:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 21:25
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.0K in / 418 out [46.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 56s
- Log: OOMPAH-796__20260804T212503Z.jsonl
---
author: oompah
created: 2026-08-04 21:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 21:31
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-04 21:41
---
Branch-topology repair: the empty implementation run was dispatched from task/parent branch a681ec2fc, which predates completed hard-start prerequisites OOMPAH-765/766/785 on epic-OOMPAH-763 f1e7925b7. No task edits or commits exist. Returning to Open revokes the stale-base run; epic-OOMPAH-770 and this task branch will be fast-forwarded to the prerequisite lineage before redispatch.
---
author: oompah
created: 2026-08-04 21:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 33, Tool calls: 22
- Tokens: 274 in / 81 out [355 total]
- Cost: $0.0000
- Exit: terminated, Duration: 10m 48s
- Log: OOMPAH-796__20260804T213133Z.jsonl
---
author: oompah
created: 2026-08-04 21:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 21:52
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-04 21:53
---
Understanding: I will trace WorkDecision evaluation, dispatch, recovery jobs, and bounded full-sync paths; implement a single totality/liveness controller that assigns exactly one allowed disposition and enqueues reason-coded remediation; then add focused regression coverage for stalls, graph impossibility, restart convergence, and idempotency.
---
author: oompah
created: 2026-08-04 21:54
---
Discovery: Found existing pure evaluator (oompah/work_decision.py), facts collector (workflow_facts.py), durable jobs (workflow_jobs.py), and scheduler (workflow_scheduler.py). Runtime currently has only shadow comparison plus legacy dispatch/watchdog paths; I am tracing initialization and tick/full-sync seams to add the universal controller without moving status writes into evaluation.
---
author: oompah
created: 2026-08-04 22:05
---
Landing-order coordination: OOMPAH-806 is already in verification with a substantial legitimate orchestrator.py/workflow_contract.py diff; this task is now reaching the same runtime seam. A finish-order dependency on OOMPAH-806 has been added without blocking current implementation. Complete your scoped work, but rebase/reconcile onto the landed OOMPAH-806 lineage before final submission/integration; preserve both transition-CAS and totality-controller semantics with combined focused tests.
---
author: oompah
created: 2026-08-04 22:07
---
Implementation: Added UniversalTotalityLivenessController with bounded rotating evaluation, generation-fenced reconciliation, ownership/graph/liveness/retry safeguards, explicit missing-job recovery, restart recovery, and structured escalation evidence. Workflow jobs now persist reason_code metadata. Enforce-mode orchestrator sweeps invoke the controller without writing tracker status; controller health is published in snapshots.
---
author: oompah
created: 2026-08-04 22:13
---
Landing order tightened to OOMPAH-806 -> OOMPAH-807 -> OOMPAH-796 because 807's audit preflight/runtime wiring also legitimately touches projects.py/orchestrator.py. Preserve your current scoped work, then rebase after both exact predecessor heads land and run the combined workflow-controller/audit/watchdog suites before final submission.
---
author: oompah
created: 2026-08-04 22:15
---
Verification: Focused workflow/controller gate passes: 169 tests passed in 38.74s across controller, decision, facts, jobs, scheduler, reasons, shadow, and orchestrator integration suites. Coverage includes all canonical non-final statuses, duplicate/missing/expired/impossible ownership, missing queue/audit/review jobs, stale facts, due/exhausted retries, cycles, restart convergence, idempotent remediation, and enforce-mode read-only tracker integration.
---
author: oompah
created: 2026-08-04 22:17
---
Completion: Delivered and pushed commit 7cdc30f36. Universal controller, durable reason-coded recovery metadata, enforce-mode dispatch integration, restart/idempotency safeguards, design notes, and regression coverage are complete. Branch is clean and up to date with origin; focused verification passed 169 tests.
---
author: oompah
created: 2026-08-04 22:17
---
Implemented universal totality/liveness controller with bounded event/full-sync evaluation, durable reason-coded remediation, ownership/graph/liveness/retry safeguards, enforce-mode dispatch integration, restart convergence, and comprehensive regression tests.
---
author: oompah
created: 2026-08-04 22:18
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 117
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 25m 53s
- Log: OOMPAH-796__20260804T215245Z.jsonl
---
author: oompah
created: 2026-08-04 23:58
---
Pre-landing combined-tree audit found acceptance blockers despite a clean patch-identical merge onto the expected 806/807 lineage. Repair before resubmission: (1) _integration_decision must treat a blocked exact-head gate as authoritative and schedule no integration_attempt until explicit same-generation retry, newer head, or repair evidence; (2) universal facts must overlay the durable IntegrationQueueStore row/lease because live tracker metadata can remain ready while the queue is integrating, otherwise the controller duplicates an active integration; (3) terminal-audit facts/tests must preserve queued/running revisionless metadata dispositions and route unsafe evidence to action_required rather than revision/transport retry. Add generation-race/restart regressions and run combined 796+806+807 suites. Task returned to Open and its OOMPAH-807 edge upgraded to hard-start so the server can repair it only from the final landed root head.
---
author: oompah
created: 2026-08-05 17:00
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-05 17:00
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 17:06
---
Understanding: I've reviewed the audit findings from the previous pass. The key issues to address are: (1) _integration_decision logic must check if a task is blocked by active integration queue state before attempting new integration_attempts; (2) Universal facts must overlay tracker integration metadata with the durable IntegrationQueueStore to prevent duplicate active integrations; (3) Terminal audit facts must preserve queued/running revisionless metadata dispositions. I'm now investigating the current implementation and testing to identify exact repairs needed.
---
author: oompah
created: 2026-08-05 18:14
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 41, Tool calls: 17
- Tokens: 334 in / 100 out [434 total]
- Cost: $0.0000
- Exit: stalled, Duration: 1h 14m 24s
- Log: OOMPAH-796__20260805T170025Z.jsonl
---
author: oompah
created: 2026-08-05 18:14
---
Agent stalled 1 time(s) (4464s (434 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-05 18:16
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-05 18:16
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 18:21
---
Understanding (attempt #1 continuation): Reviewing previous implementation (commit 7cdc30f36) against the pre-landing audit blockers. The three required fixes are: (1) _integration_decision must treat a blocked exact-head gate as action_required instead of scheduling integration_attempt; (2) WorkflowFactCollector/facts overlay must consult durable IntegrationQueueStore to prevent duplicate active integrations; (3) Terminal-audit facts must preserve queued/running revisionless metadata dispositions and route unsafe evidence to action_required. Now investigating current code to locate exact repair points.
---
author: oompah
created: 2026-08-05 18:36
---
Discovery: Identified exact repair points for all three audit blockers. (1) In _integration_decision (work_decision.py:769ff), when state==blocked and no retry_forced flag, the code falls through to the final case and schedules integration_attempt—fix: add blocked-gate detection before the fallthrough that routes to ACTION_REQUIRED with reason_code integration.gate_blocked. (2) WorkflowFactCollector.collect() reads only issue.integration from tracker; no overlay from IntegrationQueueStore—fix: add optional integration_queue_store parameter and overlay queue state/lease before constructing integration FactObservation. (3) _validation_decision has no check for quarantined/unsafe audit metadata; it falls through to validation.queued RETRY_SCHEDULED—fix: add quarantined check before the phase check, routing to ACTION_REQUIRED. Generation-race test: controller reconcile is already idempotent by generation fence; need explicit concurrent-generation regression test.
---
author: oompah
created: 2026-08-05 18:42
---
Coordinator review of the in-flight repair found one exact-generation requirement to cover before commit: WorkflowFactCollector._overlay_integration_queue currently overlays integrating/blocked solely by project+task. Fence the durable row to the issue/tracker exact head (and relevant generation/lease authority) so a stale blocked or integrating row for H1 cannot block or suppress the required attempt for newer H2. Add the generation-race regression requested in comment #20. Also ensure production construction actually supplies IntegrationQueueStore, and complete the queued/running revisionless terminal-disposition path.
---
author: oompah
created: 2026-08-05 18:42
---
Additional exact retry fence: integration.gate_blocked must remain authoritative only absent explicit same-generation retry or repair evidence. Carry retry_forced / matching repair authority into the fact and let that evidence permit the intended recovery/attempt; an unconditional state==blocked ACTION_REQUIRED would ignore OOMPAH-838 explicit retry semantics.
---
author: oompah
created: 2026-08-05 19:01
---
Additional combined-tree contract from OOMPAH-836 review: the live_claim_precedes_history incident fixture expects an active exact integration claim to take precedence over historical recovery, but current work_decision ordering evaluates historical first and production facts do not emit the flag. Resolve this in the universal fact/decision controller (or file a precise child before completion); do not leave the incident contract disconnected from production facts.
---
author: oompah
created: 2026-08-05 19:22
---
Agent stalled 1 time(s) (3959s (2106 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (attempt #2)
---
author: oompah
created: 2026-08-05 19:22
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 79, Tool calls: 48
- Tokens: 85 in / 2.0K out [2.1K total]
- Cost: $0.0000
- Exit: stalled, Duration: 1h 5m 59s
- Log: OOMPAH-796__20260805T181630Z.jsonl
---
author: oompah
created: 2026-08-05 19:23
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-08-05 19:23
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 19:40
---
Understanding (attempt #3 continuation, deep profile): Reviewing the recovery-checkpoint changes and audit feedback. Prior work landed integration.gate_blocked, quarantined/unsafe audit routing, and the IntegrationQueueStore overlay skeleton. Outstanding blockers per audit comments #20/#30/#31/#32: (1) exact-head fence for _overlay_integration_queue (stale H1 rows must not suppress required attempts for H2); (2) retry_forced bypass for gate_blocked; (3) live_claim_precedes_history must be emitted from production facts and evaluated ahead of tracker action_required in _integration_decision; (4) production WorkflowFactCollector construction sites must pass IntegrationQueueStore; (5) generation-race and restart-convergence regressions. Plan: fence overlay by head_sha, emit retry_forced+live_claim_precedes_history in fact, reorder _integration_decision, wire orchestrator.py, add tests.
---
author: oompah
created: 2026-08-05 20:20
---
Implementation: All audit blockers repaired. (1) workflow_facts.py: _overlay_integration_queue now fences the queue row to the tracker's exact head_sha - stale rows for older heads (H1) do not suppress attempts for newer heads (H2); emits retry_forced flag from durable queue authority into the fact; emits live_claim_precedes_history when the queue holds a valid integrating lease and the tracker still shows ready/queued. (2) work_decision.py: _integration_decision now evaluates live_claim_precedes_history BEFORE tracker action_required (so historical operator escalations do not evict a live owner); gate_blocked yields to retry_forced=True (OOMPAH-838 same-generation retry authority). (3) work_decision.py: terminal_audit unsafe/quarantined evidence routes to ACTION_REQUIRED with operator.action_required and its own action_code, while plain queued/running dispositions are preserved. (4) orchestrator.py: both WorkflowFactCollector construction sites now pass self.integration_queue so the overlay reaches production. Test additions: 7 tests in test_workflow_facts.py (overlay: integrating/blocked/retry_forced/stale H1 for both blocked and integrating/read-error/expired-lease/live-claim), 5 tests in test_work_decision.py (gate_blocked/retry_forced/live-claim-precedes/audit-unsafe/audit-queued-running preserved), 6 tests in test_workflow_controller.py (end-to-end gate_blocked/retry_forced/live-claim/generation-race stale H1/live-claim signaled/restart-convergence idempotent).
---
author: oompah
created: 2026-08-05 20:21
---
Verification: Focused workflow suites pass. tests/test_work_decision.py: 45 passed (5 new). tests/test_workflow_facts.py: 40 passed (7 new). tests/test_workflow_controller.py: 17 passed (6 new). tests/test_workflow_shadow_integration.py: 11 passed. tests/test_workflow_jobs.py: 30 passed. tests/test_workflow_reasons.py: 12 passed. tests/test_workflow_scheduler.py: 17 passed. tests/test_workflow_contract.py: 22 passed. tests/test_integration_queue.py: 20 passed. tests/test_workflow_incident_fixtures.py: 33 passed. Neighbour suites tests/test_orchestrator_handlers.py + test_orchestrator_conflict_repair.py + test_orchestrator_full_sync.py: 307 passed. Total focused verification: 554 tests pass. Pushed as 2af2f103d.
---
author: oompah
created: 2026-08-05 20:22
---
Completion: Delivered commit 2af2f103d addressing all pre-landing audit blockers from comments #20/#30/#31/#32. Overlay is exact-head fenced, retry_forced authority is preserved end-to-end, live_claim_precedes_history is now emitted from production facts and evaluated ahead of tracker action_required, and both WorkflowFactCollector construction sites in orchestrator.py pass the durable IntegrationQueueStore. Regression coverage: 18 new tests spanning fact overlay, decision ordering, generation-race stale-head suppression, and restart-convergence idempotency. Branch clean, pushed to origin, all focused workflow suites green (247 tests).
---
author: oompah
created: 2026-08-05 20:22
---
Fenced integration overlay to exact head, honoured retry_forced authority, wired IntegrationQueueStore into production facts, reordered live_claim_precedes_history ahead of tracker action_required, and added generation-race and restart-convergence regressions.
---
author: oompah
created: 2026-08-05 20:23
---
Agent completed successfully in 3579s (37242 tokens)
---
author: oompah
created: 2026-08-05 20:23
---
Run #3 [attempt=3, profile=deep, role=deep -> Claude/opus]
- Turns: 154, Tool calls: 111
- Tokens: 117 in / 37.1K out [37.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 59m 39s
- Log: OOMPAH-796__20260805T192450Z.jsonl
---
<!-- COMMENTS:END -->
