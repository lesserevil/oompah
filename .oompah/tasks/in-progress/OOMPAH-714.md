---
id: OOMPAH-714
type: task
status: In Progress
priority: null
title: Do not cancel an unrelated branch gate when an auditor attempt retires
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T01:03:08.223719Z'
updated_at: '2026-08-03T01:28:45.190963Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0c34ea48f316eddc2939578204da8fde3861fc49cb452febf4b382258d6d5bc8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T01:04:06.685636+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-714 describes a novel bug triggered by concurrent\
    \ auditor retirement and branch gate execution, with no matching task in the corpus\
    \ addressing the same problem of incorrect cross-task cancellation during auditor\
    \ policy exhaustion. The closest related archived work covers epic workflow orchestration\
    \ and dispatch validation, but does not overlap with quality gate ownership or\
    \ cancellation keying. This is an original issue requiring targeted investigation\
    \ and implementation in quality_gate.py and orchestrator.py.\n# Duplicate Investigation:\
    \ OOMPAH-714\n\nI'll conduct a systematic review of the task corpus to determine\
    \ whether OOMPAH-714 describes a duplicate problem.\n\n## Task Analysis\n\n**OOMPAH-714\
    \ Core Issue:**\n- Concurrent OOMPAH-709 (completion auditor) and OOMPAH-710 (branch\
    \ gate) both running\n- When OOMPAH-709 auditor exhausted policy-denial limit\
    \ and retired, oompah incorrectly cancelled OOMPAH-710's unrelated branch gate\n\
    - Root cause: missing cancellation ownership keying between auditor retirement\
    \ and branch quality gates\n- Required fix: trace cancellation across terminal-audit\
    \ retirement, running-entry termination, and BranchQualityGate generations\n\n\
    **Scope of Related Code:**\n- `oompah/quality_gate.py`: active process registry,\
    \ cancel_generation keying\n- `oompah/orchestrator.py`: terminal auditor retirement,\
    \ standalone delivery authority\n- Cross-task/cross-authority cancellation prevention\n\
    \n## Corpus Review\n\nI've reviewed all 175 tasks in the project corpus. The active\
    \ task set contains only **OOMPAH-714 (Open)**. All other tasks are in terminal\
    \ states (Archived or Done).\n\n**Excluded from consideration** (terminal state\
    \ = completed/merged work):\n- OOMPAH-1 through OOMPAH-175: all Archived or Done\n\
    \n**Closest examined tasks** (orthogonal to OOMPAH-714):\n- OOMPAH-162 (Tolerate\
    \ stacked children merged to default branch): Epic workflow \u2014 landing detection,\
    \ not cancellation ownership\n- OOMPAH-163 (Allow generated epic target branches\
    \ through dispatch): Dispatch validation, not process cancellation\n- OOMPAH-165\
    \ (Fix shared epic landed detection before main merge): Epic state detection,\
    \ not auditor/gate separation\n- OOMPAH-168 (Simplify orchestration to the shared\
    \ epic workflow): Epic orchestration strategy, not process ownership\n- OOMPAH-172\u2013\
    OOMPAH-175 (Release addendums, configurations, documentation): Infrastructure,\
    \ not gate cancellation\n\n**None of the archived tasks address:**\n- Auditor\
    \ attempt retirement and its interaction with unrelated quality gates\n- Cancellation\
    \ own"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 0bd07a03-6854-40ce-92e6-5af5958a2e6a
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1615
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1615
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1615
    cost_usd: 0.0
    recorded_at: '2026-08-03T01:04:06.684275+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-714__20260803T010338Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-714
    source_sha: 8b6f368252e653d56f0c1c9a07da0fc825a9cb10
    completed_at: '2026-08-03T01:04:06.700512+00:00'
---
## Summary

Triggered by concurrent OOMPAH-709 completion audit and OOMPAH-710 branch gate on 2026-08-03. OOMPAH-710 was actively running its exact-head isolated make test gate at 205f413440767c5c2c94c641504f96f6a71c77bb. At 00:57:41 the OOMPAH-709 auditor exhausted its policy-denial limit; at 00:57:42 Oompah logged Interrupted 1 active quality gate process group, then Discarding superseded quality gate for OOMPAH-710. The OOMPAH-710 branch and accepted head had not changed. Oompah moved on to OOMPAH-711 and surfaced standalone_ready_delivery:OOMPAH-710 saying its configured gate did not pass, stranding 710 despite no test failure.

Implementation scope:
- Trace cancellation ownership across terminal-audit retirement, running-entry termination, standalone delivery authority, and BranchQualityGate generations.
- Ensure stopping or rotating an auditor can terminate only that auditor provider process and detached audit worktree; it must never cancel a branch gate for another task.
- Key every quality-gate cancellation to the exact project/task/head/authority generation and reject cross-task or generationless cancellation outside full orchestrator shutdown.
- Treat an intentionally superseded gate as retryable for the same unchanged accepted head; do not cache it as a failed gate or strand the task with a no-active-delivery warning.
- Make active gate ownership visible in health/state so the UI can distinguish running, interrupted-for-retry, failed, and idle.

Relevant evidence: oompah.log around 2026-08-03T00:57:41Z through 00:57:45Z; oompah/quality_gate.py active process registry and cancel_generation; oompah/orchestrator.py terminal auditor retirement, standalone delivery authority revocation, and review gate handling.

Required tests:
- Run task A completion auditor concurrently with task B branch gate, exhaust or rotate A, and prove B process group survives and its result is accepted.
- Supersede B explicitly and prove only B exact generation stops.
- Interrupt B for a retryable infrastructure reason and prove unchanged accepted head is retried rather than alerted as a test failure.
- Full orchestrator shutdown still terminates every gate process group.
- State and alert tests report the correct active owner and clear after recovery.

Acceptance criteria:
- Replaying the OOMPAH-709/OOMPAH-710 sequence cannot interrupt the unrelated gate.
- A cross-task cancellation request has no effect and emits diagnostic ownership evidence.
- OOMPAH-710-style interrupted work automatically re-enters delivery without operator resubmission.
- Focused quality-gate, terminal-audit, standalone-delivery, and orchestrator tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 01:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 01:03
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 01:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 32s
- Log: OOMPAH-714__20260803T010338Z.jsonl
---
author: oompah
created: 2026-08-03 01:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 01:04
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 01:28
---
Direct owner review before integration:
1. Add a true orchestrator regression with task A auditor retirement/rotation concurrent with task B owned branch gate, proving B survives and its result is accepted; the current QualityGateOwner unit test alone does not replay the production path required by the task.
2. Bound or clear _quality_gate_outcomes/recent telemetry. As currently drafted it retains one result per project/task for the server lifetime, which is undesirable ahead of ~100-task dispatch. Preserve active/interrupted observability without unbounded historical growth.
3. Verify the exact-owner path through partial/mocked gate facades remains compatible; _cancel_standalone_delivery_gate currently invokes cancel_owner unconditionally before its documented legacy fallback.
Please address these after the current full-test process returns, then rerun the focused affected suites and make check-secrets before submission.
---
<!-- COMMENTS:END -->
