---
id: OOMPAH-838
type: bug
status: In Validation
priority: 1
title: Preserve forced quality-gate retry through integration claim
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:45:03.282492Z'
updated_at: '2026-08-05T18:16:41.672154Z'
work_branch: OOMPAH-838
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/722
review_number: '722'
review_head: 005e9e717de8cf1d77b4c3331df20ecc64c421e9
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-838
  head_sha: 005e9e717de8cf1d77b4c3331df20ecc64c421e9
  submitted_at: '2026-08-05T16:58:22.388278+00:00'
  updated_at: '2026-08-05T16:58:22.388278+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/722
oompah.review_number: '722'
oompah.work_branch: OOMPAH-838
oompah.target_branch: main
oompah.review_head: 005e9e717de8cf1d77b4c3331df20ecc64c421e9
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-4ba35f85be8a: '2026-08-05T17:58:02.650965+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-838
    target_state: Done
    evidence_fingerprint: 9cdd0a6f76b61c2936d1c07199e119d2cf827e151ecdf67ac87da479ed217647
    audit_ids:
    - audit-41bcaf72f72b
    kind: result
    applied: true
    retired_at: '2026-08-05T17:58:02.650977+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-838
    audit_id: audit-41bcaf72f72b
    attempt_id: attempt-4ba35f85be8a
    target_state: Done
    evidence_fingerprint: 9cdd0a6f76b61c2936d1c07199e119d2cf827e151ecdf67ac87da479ed217647
    status: In Validation
    audit_ids:
    - audit-41bcaf72f72b
    applied: true
    created_at: '2026-08-05T17:58:02.650994+00:00'
    applied_at: '2026-08-05T17:58:10.241542+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-41bcaf72f72b
    project_id: proj-14849f1b
    task_id: OOMPAH-838
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9cdd0a6f76b61c2936d1c07199e119d2cf827e151ecdf67ac87da479ed217647
    attempts:
    - version: 1
      attempt_id: attempt-4ba35f85be8a
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9cdd0a6f76b61c2936d1c07199e119d2cf827e151ecdf67ac87da479ed217647
      created_at: '2026-08-05T17:26:42.008601+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T17:26:42.008601+00:00'
      branch_key: OOMPAH-838
      verdict: pass
      completed_at: '2026-08-05T17:58:02.650768+00:00'
      ended_at: '2026-08-05T17:58:02.650768+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-05T17:26:12.554338+00:00'
    updated_at: '2026-08-05T17:58:02.650768+00:00'
  - version: 1
    audit_id: audit-e856e8a1a478
    project_id: proj-14849f1b
    task_id: OOMPAH-838
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9cdd0a6f76b61c2936d1c07199e119d2cf827e151ecdf67ac87da479ed217647
    attempts:
    - version: 1
      attempt_id: attempt-9540219df682
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9cdd0a6f76b61c2936d1c07199e119d2cf827e151ecdf67ac87da479ed217647
      created_at: '2026-08-05T18:16:29.936599+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T18:16:29.936599+00:00'
      branch_key: OOMPAH-838
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-05T17:26:12.554338+00:00'
    updated_at: '2026-08-05T18:16:29.936599+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-4ba35f85be8a
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9cdd0a6f76b61c2936d1c07199e119d2cf827e151ecdf67ac87da479ed217647
    created_at: '2026-08-05T17:26:42.008601+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T17:26:42.008601+00:00'
    branch_key: OOMPAH-838
  - version: 1
    attempt_id: attempt-9540219df682
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9cdd0a6f76b61c2936d1c07199e119d2cf827e151ecdf67ac87da479ed217647
    created_at: '2026-08-05T18:16:29.936599+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T18:16:29.936599+00:00'
    branch_key: OOMPAH-838
oompah.task_costs:
  total_input_tokens: 6
  total_output_tokens: 569
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 6
      output_tokens: 569
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 569
    cost_usd: 0.0
    recorded_at: '2026-08-05T17:58:48.963549+00:00'
---
## Summary

Live regression from OOMPAH-523: an explicit same-head resubmission correctly calls IntegrationQueueStore.enqueue(... explicit_retry=True) and persists retry_forced=1, but claim_next clears retry_forced before returning the claimed IntegrationQueueItem. Orchestrator._execute_integration_item therefore always passes retry_forced=False to BranchQualityGate, reuses the prior cached failed result, and immediately routes a locally verified clean head back to Needs CI Fix. The cached failure for 9ea2b5523 is a 48.94-second truncated 9%-progress run containing only PASS lines; OOMPAH-523's immediately preceding official make test passed 15,452 tests. Implementation scope: carry one-shot force-retry authority on the claimed item while atomically clearing the durable pending flag so restarts do not loop; distinguish consumed retry intent from stored ready state and preserve exact owner/head fencing. Relevant files: oompah/integration_queue.py, oompah/orchestrator.py integration claim/execution, quality-gate cache tests. Required tests: blocked same-head explicit retry bypasses a cached failed/timed-out/error result exactly once; claimed item exposes the consumed force flag while the persisted integrating row no longer advertises a pending retry; crash/recovery does not loop; normal/new-head claims remain unforced; OOMPAH-523 regression. Acceptance: an explicit same-head resubmission executes a fresh exact gate instead of replaying cached failure, and a passing gate can integrate naturally without manual cache deletion or fake commits.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 16:58
---
Implemented one-shot forced gate retry handoff with exact SQLite claim fencing. The durable retry flag is consumed atomically at claim, an ephemeral claimed authority reaches the executor, crash recovery cannot loop, and the returned head/lease cannot race with another connection's replacement. Independent re-review found no blockers. Verification: 43 focused queue/executor tests passed; terminal mutation scan passed 8/8.
---
author: oompah
created: 2026-08-05 16:58
---
Preserved one-shot forced quality-gate retry through exact fenced integration claims; 43 focused tests and terminal mutation scan pass.
---
author: oompah
created: 2026-08-05 16:58
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-838`
Target: `main`
Head: `005e9e717de8cf1d77b4c3331df20ecc64c421e9`
Command: `make test`
Result: `infrastructure_error`

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Trusted quality-gate runtime corruption detected; candidate CI was not run: trusted editable source mapping is inconsistent: expected one of ['/home/shedwards/src/oompah'] or immutable candidate /home/shedwards/.oompah/tmp/oompah-quality-gate-k34subi4/workspace; actual /home/shedwards/.oompah/worktrees/oompah/OOMPAH-838. Repair or replace the service test runtime before rerunning the branch gate.
```
---
author: oompah
created: 2026-08-05 17:16
---
Branch quality gate passed for `005e9e717de8cf1d77b4c3331df20ecc64c421e9` using `make test` in 635.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-05 17:26
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 17:26
---
YOLO: merged PR #722.
---
author: oompah
created: 2026-08-05 17:26
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 17:27
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 17:58
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_sha: 005e9e717de8cf1d77b4c3331df20ecc64c421e9
- merge_commit: b53bdbc77
- pr: PR #722
- make_test: 15660 passed, 7 skipped, 1 xfailed, 55 warnings in 622.19s
- terminal_mutation_scan: 8 identified, 8 explicitly allowlisted (pass)
- changed_files: oompah/integration_queue.py, oompah/orchestrator.py, tests/test_integration_queue.py, tests/test_integration_executor.py
- regression_test: test_claimed_explicit_retry_bypasses_cached_gate_failure (OOMPAH-523)
- claim_fence: UPDATE, SELECT, COMMIT all inside single BEGIN IMMEDIATE; claimed_retry_forced carried on returned item only
- durable_flag_state_after_claim: retry_forced=0 in row (verified by test_retry_forced_is_returned_once_and_consumed_by_claim and integrating.retry_forced is False assertions)
- orchestrator_call_site: oompah/orchestrator.py:11059 retry_forced=item.claimed_retry_forced
---
author: oompah
created: 2026-08-05 17:58
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 35, Tool calls: 23
- Tokens: 6 in / 569 out [575 total]
- Cost: $0.0000
- Exit: normal, Duration: 31m 55s
- Log: OOMPAH-838__20260805T172702Z.jsonl
---
author: oompah
created: 2026-08-05 18:16
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 18:16
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
