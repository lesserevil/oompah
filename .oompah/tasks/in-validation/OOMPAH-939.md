---
id: OOMPAH-939
type: task
status: In Validation
priority: null
title: Continue saturated durable workflow batches without full-sync delay
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T08:54:39.101794Z'
updated_at: '2026-08-09T13:05:51.184423Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-4827a2c0df9f
    project_id: proj-14849f1b
    task_id: OOMPAH-939
    digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
  - version: 1
    audit_id: audit-bd560d2bb335
    project_id: proj-14849f1b
    task_id: OOMPAH-939
    digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-939","audit-4827a2c0df9f","attempt-8219358c7bea"]': '2026-08-09T11:10:55.552055+00:00'
    '["proj-14849f1b","OOMPAH-939","audit-bd560d2bb335","attempt-cd9094da20a7"]': '2026-08-09T11:52:12.431727+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-939
    target_state: Done
    evidence_fingerprint: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
    audit_ids:
    - audit-4827a2c0df9f
    kind: result
    applied: true
    retired_at: '2026-08-09T11:10:55.552071+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-939
    audit_id: audit-4827a2c0df9f
    attempt_id: attempt-8219358c7bea
    target_state: Done
    evidence_fingerprint: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
    status: In Validation
    audit_ids:
    - audit-4827a2c0df9f
    kind: result
    applied: true
    created_at: '2026-08-09T11:10:55.552081+00:00'
    applied_at: '2026-08-09T11:11:05.730223+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-4827a2c0df9f
    project_id: proj-14849f1b
    task_id: OOMPAH-939
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
    attempts:
    - version: 1
      attempt_id: attempt-70a86da90e2f
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
      created_at: '2026-08-09T09:44:34.011942+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T09:44:34.011942+00:00'
      branch_key: OOMPAH-939
      selected_ref: origin/OOMPAH-939
      selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
      failure_classification: finalization_failure
      ended_at: '2026-08-09T10:08:52.377768+00:00'
      failure_reason: normal
      next_retry_at: '2026-08-09T10:09:02.377739+00:00'
    - version: 1
      attempt_id: attempt-97ac7977bd6f
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
      created_at: '2026-08-09T10:10:58.281356+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T10:10:58.281356+00:00'
      branch_key: OOMPAH-939
      selected_ref: origin/OOMPAH-939
      selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
      candidate_rotation_count: 1
      failure_classification: finalization_failure
      ended_at: '2026-08-09T10:37:15.112396+00:00'
      failure_reason: normal
      next_retry_at: '2026-08-09T10:37:35.112365+00:00'
    - version: 1
      attempt_id: attempt-8219358c7bea
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
      created_at: '2026-08-09T10:45:18.785995+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T10:45:18.785995+00:00'
      branch_key: OOMPAH-939
      selected_ref: origin/OOMPAH-939
      selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
      candidate_rotation_count: 2
      verdict: pass
      completed_at: '2026-08-09T11:10:55.551930+00:00'
      ended_at: '2026-08-09T11:10:55.551930+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-09T09:39:27.270044+00:00'
    selected_ref: origin/OOMPAH-939
    selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
    updated_at: '2026-08-09T11:10:55.551930+00:00'
  - version: 1
    audit_id: audit-bd560d2bb335
    project_id: proj-14849f1b
    task_id: OOMPAH-939
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
    attempts:
    - version: 1
      attempt_id: attempt-cd9094da20a7
      target_state: Merged
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
      created_at: '2026-08-09T11:31:45.949124+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T11:31:45.949124+00:00'
      branch_key: OOMPAH-939
      selected_ref: origin/OOMPAH-939
      selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
      verdict: fail
      failure_classification: infrastructure_error
      ended_at: '2026-08-09T11:52:12.431629+00:00'
      failure_reason: retry ceiling reached; verdict left pending
    - version: 1
      attempt_id: attempt-289bbb15fed0
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
      created_at: '2026-08-09T13:05:42.998564+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-09T13:05:42.998564+00:00'
      branch_key: OOMPAH-939
      selected_ref: origin/OOMPAH-939
      selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
      candidate_rotation_count: 1
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-09T09:39:27.270044+00:00'
    selected_ref: origin/OOMPAH-939
    selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
    updated_at: '2026-08-09T13:05:42.998564+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-70a86da90e2f
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
    created_at: '2026-08-09T09:44:34.011942+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T09:44:34.011942+00:00'
    branch_key: OOMPAH-939
    selected_ref: origin/OOMPAH-939
    selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
    failure_classification: finalization_failure
    ended_at: '2026-08-09T10:08:52.377768+00:00'
    failure_reason: normal
    next_retry_at: '2026-08-09T10:09:02.377739+00:00'
  - version: 1
    attempt_id: attempt-97ac7977bd6f
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
    created_at: '2026-08-09T10:10:58.281356+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T10:10:58.281356+00:00'
    branch_key: OOMPAH-939
    selected_ref: origin/OOMPAH-939
    selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
    candidate_rotation_count: 1
    failure_classification: finalization_failure
    ended_at: '2026-08-09T10:37:15.112396+00:00'
    failure_reason: normal
    next_retry_at: '2026-08-09T10:37:35.112365+00:00'
  - version: 1
    attempt_id: attempt-8219358c7bea
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
    created_at: '2026-08-09T10:45:18.785995+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T10:45:18.785995+00:00'
    branch_key: OOMPAH-939
    selected_ref: origin/OOMPAH-939
    selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
    candidate_rotation_count: 2
  - version: 1
    attempt_id: attempt-cd9094da20a7
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
    created_at: '2026-08-09T11:31:45.949124+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T11:31:45.949124+00:00'
    branch_key: OOMPAH-939
    selected_ref: origin/OOMPAH-939
    selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
  - version: 1
    attempt_id: attempt-289bbb15fed0
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
    created_at: '2026-08-09T13:05:42.998564+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-09T13:05:42.998564+00:00'
    branch_key: OOMPAH-939
    selected_ref: origin/OOMPAH-939
    selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
    candidate_rotation_count: 1
oompah.task_costs:
  total_input_tokens: 664
  total_output_tokens: 23839
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 664
      output_tokens: 23839
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 10
    output_tokens: 131
    cost_usd: 0.0
    recorded_at: '2026-08-09T10:08:50.100539+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 330
    output_tokens: 12834
    cost_usd: 0.0
    recorded_at: '2026-08-09T10:37:11.522940+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 314
    output_tokens: 10684
    cost_usd: 0.0
    recorded_at: '2026-08-09T11:11:14.086278+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 10
    output_tokens: 190
    cost_usd: 0.0
    recorded_at: '2026-08-09T11:52:39.653299+00:00'
---
## Summary

Triggered by: OOMPAH-785\n\nProduction regression observed on 2026-08-09 while recovering the legacy Done backlog after OOMPAH-935: WorkflowRuntime._run_due processed exactly the configured 32-job batch cap, left current claimable Oompah jobs queued/due, and then remained idle until the independent 300-second FULL_SYNC safety net. The runtime transition observer wakes only for transition_applied; batches made entirely of retry/superseded/no-transition results emit no wake. _run_due reports processed but no saturation/continuation signal, so bounded work can be stranded for five minutes despite worker.accepting=true.\n\nImplementation scope: preserve bounded batches and project fairness; make the durable runtime report when a batch reaches its cap and may have more eligible work; after the current durable tick publishes its report/metrics, request exactly one coalesced REFRESH_REQUESTED continuation through the production orchestrator event loop. Do not recurse inside the tick and do not spin from raw queued counts because those include paused projects, future retries, and ineligible actions. Suppress continuation during drain/shutdown and expose bounded observability such as batch_saturated/continuation_requested. Relevant files: oompah/workflow_runtime.py, oompah/orchestrator.py, scheduler/runtime tests.\n\nRequired tests: seed more than one batch of current claimable jobs whose handlers complete/retry/supersede without transition events; prove the first production tick processes the cap and posts one coalesced continuation; prove the next tick immediately handles the suffix without FULL_SYNC; prove paused-project, future-retry, and ineligible rows do not cause a loop; preserve multi-project fairness and shutdown/drain fencing.\n\nAcceptance: current eligible work never waits for the five-minute safety net solely because the prior batch hit its cap; each continuation remains bounded/coalesced and non-recursive; no busy loop occurs for non-claimable rows; focused and complete branch gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 08:55
---
Accepted as the live batch-continuation regression found during OOMPAH-935 rollout.
---
author: oompah
created: 2026-08-09 09:03
---
Direct-owner fix is committed and pushed at 2bac503b1 on protected-main PR 751. The runtime now reports cap saturation and the production orchestrator posts one coalesced, shutdown-fenced continuation; future-due/ineligible rows do not rearm. Verification: 109 adjacent tests passed plus targeted lint/diff checks. Hosted complete gates are starting.
---
author: oompah
created: 2026-08-09 09:03
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-939`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`
Process: ended without subprocess exit evidence

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
author: oompah
created: 2026-08-09 09:19
---
Published reviewed head b1fc26aa on PR #751. The continuation path now preserves durable cross-project fairness with an explicit runnable-project allowlist; the production dispatch-loop test proves an exact-cap batch posts and consumes one coalesced refresh without waiting for the 5-minute full sync. Focused/adjacent result: 221 passed; targeted undefined-name lint passed. Independent re-review approved; hosted 3.11/3.12/3.13 gates are running with auto-merge enabled.
---
author: oompah
created: 2026-08-09 09:39
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 09:44
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 09:44
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 10:08
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 66, Tool calls: 20
- Tokens: 10 in / 131 out [141 total]
- Cost: $0.0000
- Exit: normal, Duration: 24m 13s
- Log: OOMPAH-939__20260809T094447Z.jsonl
---
author: oompah
created: 2026-08-09 10:08
---
Auditor attempt ended: auditor exited (normal) without a result. A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-09 10:11
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 10:11
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 10:37
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 124, Tool calls: 42
- Tokens: 330 in / 12.8K out [13.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 26m 10s
- Log: OOMPAH-939__20260809T101110Z.jsonl
---
author: oompah
created: 2026-08-09 10:37
---
Auditor attempt ended: auditor exited (normal) without a result. A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-09 10:45
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 10:45
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 11:11
---
Audit PASS — Done

OOMPAH-939 implementation verified: saturated durable workflow batches now continue immediately without 5-minute full-sync delay. Runtime reports batch_saturated, orchestrator posts coalesced REFRESH_REQUESTED with shutdown fencing. All 8 batch-continuation tests passed; 18,894 total tests passed (7 pre-existing infrastructure failures in test_pytest_parallel.py unrelated to this change). Acceptance criteria met: no starvation, bounded/coalesced continuation, non-recursive, multi-project fairness preserved.

Safe evidence:
- test_results: 18894_passed_7_failed_8_batch_continuation_tests_all_passed
- implementation: runtime_batch_saturated_at_workflow_runtime_3087_orchestrator_refresh_requested_event_shutdown_fenced
- acceptance_criteria: no_starvation_bounded_coalesced_non_recursive_fairness_preserved
---
author: oompah
created: 2026-08-09 11:11
---
Run #3 [attempt=3, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 81, Tool calls: 38
- Tokens: 314 in / 10.7K out [11.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 25m 53s
- Log: OOMPAH-939__20260809T104529Z.jsonl
---
author: oompah
created: 2026-08-09 11:31
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 11:31
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 11:52
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 32, Tool calls: 11
- Tokens: 10 in / 190 out [200 total]
- Cost: $0.0000
- Exit: normal, Duration: 20m 51s
- Log: OOMPAH-939__20260809T113157Z.jsonl
---
author: oompah
created: 2026-08-09 13:05
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-09 13:05
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
