---
id: OOMPAH-796
type: feature
status: In Progress
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
updated_at: '2026-08-05T18:14:28.067783Z'
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
oompah.agent_run_id: 1e438b28-a341-4eef-a29b-93fca1634730
oompah.work_branch: epic-OOMPAH-770--task-OOMPAH-796
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-770--task-OOMPAH-796
  base_branch: epic-OOMPAH-770
  base_sha: f1e7925b7263f980517f943291102c8c83335ed2
  updated_at: '2026-08-05T17:00:07.854053+00:00'
oompah.task_costs:
  total_input_tokens: 46596
  total_output_tokens: 599
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46596
      output_tokens: 599
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
<!-- COMMENTS:END -->
