---
id: OOMPAH-956
type: bug
status: Done
priority: 1
title: Do not consume workflow failure attempts for administrative deferrals
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T11:50:18.472017Z'
updated_at: '2026-08-09T16:30:20.450231Z'
work_branch: OOMPAH-956
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-956
  base_branch: epic-OOMPAH-940
  base_sha: 41a158291ad932b232e9ebc4dcff5b0357d9f57b
  head_sha: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
  submitted_at: '2026-08-09T12:07:19.976703+00:00'
  updated_at: '2026-08-09T12:07:19.976703+00:00'
oompah.work_branch: OOMPAH-956
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-aa39a2da406b
    project_id: proj-14849f1b
    task_id: OOMPAH-956
    digest: 63b4d438cd1ac27bc9e42a318fb6f37af999c59f4f540a56fa343312be353f0a
  oompah.terminal_override_records:
  - version: 1
    override_id: override-855495f157ea
    project_id: proj-14849f1b
    task_id: OOMPAH-956
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 63b4d438cd1ac27bc9e42a318fb6f37af999c59f4f540a56fa343312be353f0a
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner override after exact range-diff mapped accepted head 60b94b8844af30c1ff796869eeab3b68b98dbe1f
      to aggregate commit cc9188123 (only a duplicate-import context adjustment after
      OOMPAH-955 composition); aggregate head 2dd74be288b81265ea4a242d7467ecc1ed9f1435
      merged by PR #757 as ba0859da9d47d3417a50bfbaa2cb10a7a32f5f01 with hosted Python
      3.11/3.12/3.13 checks successful.'
    created_at: '2026-08-09T16:30:16.541673+00:00'
    selected_ref: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
    selected_sha: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-aa39a2da406b
    project_id: proj-14849f1b
    task_id: OOMPAH-956
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 63b4d438cd1ac27bc9e42a318fb6f37af999c59f4f540a56fa343312be353f0a
    attempts:
    - version: 1
      attempt_id: attempt-9b6cd3a95d81
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 63b4d438cd1ac27bc9e42a318fb6f37af999c59f4f540a56fa343312be353f0a
      created_at: '2026-08-09T14:33:47.341913+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T14:33:47.341913+00:00'
      branch_key: OOMPAH-956
      selected_ref: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
      selected_sha: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
      failure_classification: scheduler_pause
      ended_at: '2026-08-09T15:51:01.447747+00:00'
      failure_reason: graceful restart interrupted auditor before verdict
    - version: 1
      attempt_id: attempt-c37e34d773a7
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 63b4d438cd1ac27bc9e42a318fb6f37af999c59f4f540a56fa343312be353f0a
      created_at: '2026-08-09T16:07:47.745856+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T16:07:47.745856+00:00'
      branch_key: OOMPAH-956
      selected_ref: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
      selected_sha: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
      candidate_rotation_count: 1
      failure_classification: scheduler_pause
      ended_at: '2026-08-09T16:25:35.293927+00:00'
      failure_reason: operator pause interrupted auditor before verdict
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Ready to Integrate
    created_at: '2026-08-09T12:51:55.985811+00:00'
    selected_ref: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
    selected_sha: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
    updated_at: '2026-08-09T16:25:35.293927+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-9b6cd3a95d81
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 63b4d438cd1ac27bc9e42a318fb6f37af999c59f4f540a56fa343312be353f0a
    created_at: '2026-08-09T14:33:47.341913+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T14:33:47.341913+00:00'
    branch_key: OOMPAH-956
    selected_ref: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
    selected_sha: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
    failure_classification: scheduler_pause
    ended_at: '2026-08-09T15:51:01.447747+00:00'
    failure_reason: graceful restart interrupted auditor before verdict
  - version: 1
    attempt_id: attempt-c37e34d773a7
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 63b4d438cd1ac27bc9e42a318fb6f37af999c59f4f540a56fa343312be353f0a
    created_at: '2026-08-09T16:07:47.745856+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T16:07:47.745856+00:00'
    branch_key: OOMPAH-956
    selected_ref: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
    selected_sha: 60b94b8844af30c1ff796869eeab3b68b98dbe1f
    candidate_rotation_count: 1
    failure_classification: scheduler_pause
    ended_at: '2026-08-09T16:25:35.293927+00:00'
    failure_reason: operator pause interrupted auditor before verdict
oompah.task_costs:
  total_input_tokens: 92
  total_output_tokens: 12
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 92
      output_tokens: 12
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 46
    output_tokens: 7
    cost_usd: 0.0
    recorded_at: '2026-08-09T15:50:58.711396+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 46
    output_tokens: 5
    cost_usd: 0.0
    recorded_at: '2026-08-09T16:26:18.946583+00:00'
---
## Summary

Live production evidence on 2026-08-09: OOMPAH-947 and OOMPAH-949 each consumed four of five durable workflow attempts solely across administrative quiesce/restart windows, with last_error reporting that the durable workflow project was paused or quiesced, leaving only one attempt for substantive work. No active task covers general workflow effects; terminal-auditor-specific historical tasks do not address this path. Scope: classify pre-effect administrative pause, quiesce, lifecycle drain, and equivalent resource deferrals as non-substantive retry/checkpoint events that do not consume the handler failure budget. Preserve immutable history and observability, exact job generation/lease fencing, exponential retry scheduling, fail-closed treatment of uncertain post-effect outcomes, and real handler failure exhaustion. Required tests: more than max_attempts pause/quiesce/restart cycles leave the exact job claimable and preserve its checkpoint; genuine pre/post-effect handler failures increment and exhaust as designed; uncertain effect commit remains fail-closed; ABA/replacement generations are unaffected; resume posts bounded continuation and naturally executes work. Acceptance: lifecycle administration cannot strand valid work by spending its substantive retry budget, while genuine failures still converge to exhausted according to policy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 12:07
---
Implemented and pushed 60b94b8844af30c1ff796869eeab3b68b98dbe1f on OOMPAH-956. Proven pre-effect pause/quiesce/lifecycle/resource deferrals now restore claim-time attempts, preserve exact checkpoints/generation, append immutable administrative_deferred events, and retain capped exponential backoff. Genuine failures and uncertain post-effect outcomes still consume/exhaust attempts; exact lease, restart, ABA, and replacement fencing are covered. Verification: 186 focused workflow job/worker/runtime tests passed; 8 new targeted regressions passed; terminal-audit scan and secret scan passed. Additional incident corpus: 43/44 passed, with only the known sibling OOMPAH-748 containment regression on the epic base (fixed independently at dccbeb5).
---
author: oompah
created: 2026-08-09 12:07
---
Pushed 60b94b884: administrative pre-effect deferrals no longer consume workflow failure attempts; exact checkpoint/generation/lease fencing, immutable event history, capped exponential backoff, substantive failure exhaustion, and post-effect fail-closed behavior are regression covered. Focused workflow suites: 186 passed; scans passed.
---
author: oompah
created: 2026-08-09 12:16
---
Independent review found no blockers at 60b94b8844af30c1ff796869eeab3b68b98dbe1f against exact epic base 41a158291. Lease-token mutation, administrative attempt restoration, checkpoint/generation preservation, append-only deferral history/backoff, pre-effect classification, and post-effect fail-closed behavior are coherent; targeted tests cover repeated administrative cycles, ABA/restart, pause-after-claim, genuine exhaustion, and uncertain apply.
---
author: oompah
created: 2026-08-09 12:51
---
Worked around OOMPAH-958 durable integration lease deadlock: the accepted change is semantically identical in origin/epic-OOMPAH-940 at 1ab5776d8; range-diff differs only because DurableWorkflowWorker was already imported by OOMPAH-955. Reconciled to Done from authoritative target evidence.
---
author: oompah
created: 2026-08-09 12:52
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 14:33
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 14:33
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 15:51
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 5, Tool calls: 2
- Tokens: 46 in / 7 out [53 total]
- Cost: $0.0000
- Exit: scheduler_pause, Duration: 1h 17m 5s
- Log: OOMPAH-956__20260809T143403Z.jsonl
---
author: oompah
created: 2026-08-09 15:51
---
Auditor attempt ended: graceful restart interrupted auditor before verdict. A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-09 16:07
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 16:07
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 16:26
---
Auditor transport/finalization ended before a verdict; the bounded audit retry will preserve candidate capacity.
---
author: oompah
created: 2026-08-09 16:26
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 2
- Tokens: 46 in / 5 out [51 total]
- Cost: $0.0000
- Exit: terminated, Duration: 18m 28s
- Log: OOMPAH-956__20260809T160803Z.jsonl
---
<!-- COMMENTS:END -->
