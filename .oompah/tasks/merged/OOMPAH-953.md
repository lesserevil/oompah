---
id: OOMPAH-953
type: bug
status: Merged
priority: 1
title: Keep quality-gate cancellation polling local and bounded
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T11:17:05.346841Z'
updated_at: '2026-08-09T16:34:06.152243Z'
work_branch: OOMPAH-953
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/764
review_number: '764'
review_head: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-953
  head_sha: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
  submitted_at: '2026-08-09T11:37:01.843657+00:00'
  updated_at: '2026-08-09T11:37:01.843657+00:00'
oompah.work_branch: OOMPAH-953
oompah.review_url: https://github.com/lesserevil/oompah/pull/764
oompah.review_number: '764'
oompah.target_branch: main
oompah.review_head: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-b540d9ce7512
    project_id: proj-14849f1b
    task_id: OOMPAH-953
    digest: 5f96aa11fbbf50f981a8528ce23a93e02195af2d24c93421c2b271417f65a8da
  - version: 1
    audit_id: audit-865e79362ee3
    project_id: proj-14849f1b
    task_id: OOMPAH-953
    digest: 5f96aa11fbbf50f981a8528ce23a93e02195af2d24c93421c2b271417f65a8da
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-953","audit-b540d9ce7512","attempt-e7f8e915010a"]': '2026-08-09T16:03:31.001410+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-953
    target_state: Done
    evidence_fingerprint: 5f96aa11fbbf50f981a8528ce23a93e02195af2d24c93421c2b271417f65a8da
    audit_ids:
    - audit-b540d9ce7512
    kind: result
    applied: true
    retired_at: '2026-08-09T16:03:31.001443+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-953
    target_state: Merged
    evidence_fingerprint: 5f96aa11fbbf50f981a8528ce23a93e02195af2d24c93421c2b271417f65a8da
    audit_ids:
    - audit-b540d9ce7512
    - audit-865e79362ee3
    kind: override
    applied: true
    retired_at: '2026-08-09T16:34:02.991818+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-953
    audit_id: audit-b540d9ce7512
    attempt_id: attempt-e7f8e915010a
    target_state: Done
    evidence_fingerprint: 5f96aa11fbbf50f981a8528ce23a93e02195af2d24c93421c2b271417f65a8da
    status: In Validation
    audit_ids:
    - audit-b540d9ce7512
    kind: result
    applied: true
    created_at: '2026-08-09T16:03:31.001462+00:00'
    applied_at: '2026-08-09T16:03:41.916375+00:00'
    retired_by_override: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-8bd6633fa02f
    project_id: proj-14849f1b
    task_id: OOMPAH-953
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5f96aa11fbbf50f981a8528ce23a93e02195af2d24c93421c2b271417f65a8da
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner override after exact task head 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
      was proven to be PR #764 head and contained in main; PR #764 merged as 1de571bad9bdc4ae3e62599ddf0dee7fbda53f02
      with hosted Python 3.11/3.12/3.13 checks successful; the independent terminal
      auditor also recorded PASS.'
    created_at: '2026-08-09T16:33:51.109919+00:00'
    selected_ref: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
    selected_sha: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
    applied: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b540d9ce7512
    project_id: proj-14849f1b
    task_id: OOMPAH-953
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5f96aa11fbbf50f981a8528ce23a93e02195af2d24c93421c2b271417f65a8da
    attempts:
    - version: 1
      attempt_id: attempt-e7f8e915010a
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5f96aa11fbbf50f981a8528ce23a93e02195af2d24c93421c2b271417f65a8da
      created_at: '2026-08-09T15:58:42.069259+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T15:58:42.069259+00:00'
      branch_key: OOMPAH-953
      selected_ref: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
      selected_sha: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
      verdict: pass
      completed_at: '2026-08-09T16:03:31.001111+00:00'
      ended_at: '2026-08-09T16:03:31.001111+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T12:39:47.931468+00:00'
    selected_ref: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
    selected_sha: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
    updated_at: '2026-08-09T16:03:31.001111+00:00'
  - version: 1
    audit_id: audit-865e79362ee3
    project_id: proj-14849f1b
    task_id: OOMPAH-953
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5f96aa11fbbf50f981a8528ce23a93e02195af2d24c93421c2b271417f65a8da
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T12:39:47.931468+00:00'
    selected_ref: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
    selected_sha: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
    updated_at: '2026-08-09T16:34:02.991785+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-e7f8e915010a
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5f96aa11fbbf50f981a8528ce23a93e02195af2d24c93421c2b271417f65a8da
    created_at: '2026-08-09T15:58:42.069259+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T15:58:42.069259+00:00'
    branch_key: OOMPAH-953
    selected_ref: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
    selected_sha: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 216
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 10
      output_tokens: 216
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 10
    output_tokens: 216
    cost_usd: 0.0
    recorded_at: '2026-08-09T16:04:06.781847+00:00'
---
## Summary

Live OOMPAH-946 delivery made 197 GitHub branch-head requests from 11:04:00 through 11:09:51 while waiting for and running one exact branch gate. ValidationResourceLease.acquire polls is_cancelled every 50 ms and BranchQualityGate polls again every 100 ms, but the standalone callback calls _standalone_delivery_authorized, which invalidates/refetches the native task graph and invokes the remote head_resolver. Normal cancellation liveness therefore creates unbounded tracker/forge I/O, log volume, event-loop pressure, and rate-limit exposure. Scope: split a cheap local cancellation predicate (exact in-memory authority identity/revoked flag, workflow generation, and durable lease cancellation) from expensive full tracker/dependency/remote revalidation; use only the cheap predicate inside tight lease/gate loops; retain exact full tracker, dependency, and remote-head barriers immediately before snapshot/command spawn and after a passing result. Preserve prompt local revocation, exact-head fencing, stale workflow rejection, and fail-closed remote changes. Relevant code: oompah/validation_resource_lease.py acquire polling, oompah/quality_gate.py wait/run cancellation, oompah/orchestrator.py standalone delivery authority and gate callbacks. Required tests: hold validation capacity and run a gate while asserting tracker and remote resolver calls remain O(1); exact local revocation cancels promptly; workflow authority changes cancel; a remote head change before execution or after PASS is rejected; no stale review is created. Acceptance: cancellation latency remains bounded without network-backed hot polling, full exact revalidation still fences every external effect, focused lease/gate/standalone suites and terminal/secret scans pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 11:36
---
Implemented the local/full quality-gate authority split in the isolated OOMPAH-953 worktree. Tight 50/100ms lease/process loops now use exact local/workflow cancellation only; full tracker, dependency, project, and remote-head CAS checks run at pre-snapshot, pre-spawn, post-PASS, and the caller's final review boundary. Deterministic tests prove zero full reads while capacity-blocked and exactly three across execution, prompt local cancellation, workflow generation loss without graph I/O, and existing force-push/no-stale-review fences. Validation so far: 776 focused quality-gate/standalone/lease tests + 175 integration workflow/worker/recovery tests pass; terminal status mutation scan and secret scan pass. Awaiting independent no-blocker review before commit/submit.
---
author: oompah
created: 2026-08-09 11:36
---
Independent review found no blockers. Reviewed commit 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c is pushed on origin/OOMPAH-953. Focused validation: 776 quality-gate/standalone/validation-lease tests and 175 integration-workflow/worker/delivery-recovery tests passed; terminal task-status mutation scan and secret scan passed.
---
author: oompah
created: 2026-08-09 11:37
---
Separated hot quality-gate cancellation polling from full tracker/dependency/remote revalidation, retained exact external-effect barriers, and added deterministic bounded-I/O and prompt-revocation coverage.
---
author: oompah
created: 2026-08-09 12:31
---
Branch quality gate passed for `20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c` using `make test` in 160.1s. Review creation may proceed.
---
author: oompah
created: 2026-08-09 12:39
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 15:58
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 15:58
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 16:03
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- implementation_scope: local_predicate=_standalone_delivery_locally_authorized checks revoked flag identity workflow_authority_check only; polling_usage=is_cancelled in BranchQualityGate.run ValidationResourceLease.acquire for 50/100ms loops; full_revalidation=_standalone_delivery_authorized at external-effect boundaries
- test_coverage: test_capacity_wait_and_running_gate_keep_full_revalidation_o1 proves zero tracker calls during 120ms capacity wait exactly three calls across execution; test_workflow_authority_change_is_a_local_cancellation proves immediate workflow generation cancellation; 776 quality-gate tests 175 integration tests terminal secret scans passed
- requirements_satisfied: local_cheap_predicate implemented in hot loops; bounded_polling via local predicate only; external_barriers retain full revalidation; prompt_revocation without network latency; exact_head_fencing preserved; fail_closed_remote preserved
- evidence: authoritative_gate_passed full_gate_160.1s independent_review_no_blockers accepted_head_20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
---
author: oompah
created: 2026-08-09 16:04
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 99, Tool calls: 45
- Tokens: 10 in / 216 out [226 total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 18s
- Log: OOMPAH-953__20260809T155858Z.jsonl
---
author: oompah
created: 2026-08-09 16:34
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Project-owner override after exact task head 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c was proven to be PR #764 head and contained in main; PR #764 merged as 1de571bad9bdc4ae3e62599ddf0dee7fbda53f02 with hosted Python 3.11/3.12/3.13 checks successful; the independent terminal auditor also recorded PASS.
---
<!-- COMMENTS:END -->
