---
id: OOMPAH-629
type: bug
status: Done
priority: 1
title: Reject cross-task branch evidence before integration mutation
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T23:07:33.040594Z'
updated_at: '2026-08-03T20:05:09.867539Z'
work_branch: epic-OOMPAH-585
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.integration:
  version: 1
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-585--task-OOMPAH-629
  base_branch: epic-OOMPAH-585
  base_sha: d8d265b9a1957560206eec2b4da5d833942c82ea
  head_sha: 4510fb912aebc99dce90df1dc55e8ee952408401
  integrated_sha: 4510fb912aebc99dce90df1dc55e8ee952408401
  submitted_at: '2026-07-30T23:16:41.615917+00:00'
  updated_at: '2026-07-30T23:21:22.209470+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-ae148de48645: '2026-07-30T23:26:07.576810+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-870d0603e2a6
    project_id: proj-14849f1b
    task_id: OOMPAH-629
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cf489bbbd6f112ba3419b851639695c64ff67df83a6893770c6eaae808dfd57f
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup
      contains this previously audited Done child; durable integration-queue/rollup
      evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:29:16.574788+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-629
    target_state: Merged
    evidence_fingerprint: cf489bbbd6f112ba3419b851639695c64ff67df83a6893770c6eaae808dfd57f
    audit_ids:
    - audit-97cc9a57b420
    kind: override
    applied: true
    retired_at: '2026-08-02T18:29:22.653309+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-97cc9a57b420
    project_id: proj-14849f1b
    task_id: OOMPAH-629
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 52d425f1f9dc8576e99acbfc38ef7f991fe8839fbc7f09f7b839c5002f8e2e13
    attempts:
    - version: 1
      attempt_id: attempt-ae148de48645
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 52d425f1f9dc8576e99acbfc38ef7f991fe8839fbc7f09f7b839c5002f8e2e13
      created_at: '2026-07-30T23:21:36.685160+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T23:21:36.685160+00:00'
      branch_key: OOMPAH-629
      verdict: pass
      completed_at: '2026-07-30T23:26:07.576638+00:00'
      ended_at: '2026-07-30T23:26:07.576638+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T23:21:23.465705+00:00'
    updated_at: '2026-07-30T23:26:07.576638+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ae148de48645
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 52d425f1f9dc8576e99acbfc38ef7f991fe8839fbc7f09f7b839c5002f8e2e13
    created_at: '2026-07-30T23:21:36.685160+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T23:21:36.685160+00:00'
    branch_key: OOMPAH-629
oompah.task_costs:
  total_input_tokens: 61
  total_output_tokens: 11348
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 61
      output_tokens: 11348
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 61
    output_tokens: 11348
    cost_usd: 0.0
    recorded_at: '2026-07-30T23:26:20.197366+00:00'
oompah.work_branch: epic-OOMPAH-585
---
## Summary

Implementation scope: enforce the task-to-branch authority boundary before persisting submission metadata or leasing an integration row. The CLI and server submission path must reject a task identifier whose local/pushed task_branch does not equal the canonical issue work_branch (or another explicitly authorized canonical branch form), and the integration executor must never move the target task worktree or branch pointer when presented with foreign branch evidence. Preserve valid rebased task heads and normal explicit retry/rearm behavior. Relevant files include task CLI git-evidence construction, server submit validation, integration executor worktree preparation, and authority diagnostics. Reproducer: issuing 'oompah task submit OOMPAH-602' from the clean OOMPAH-593 worktree was accepted, wrote OOMPAH-593 branch/head into OOMPAH-602, then failed during integration after moving OOMPAH-602's local branch/HEAD to the foreign head; no foreign commit reached the epic. Tests: cover CLI wrong-worktree submission, direct API foreign branch evidence, pre-mutation rejection, unchanged tracker/queue/worktree/branch pointers after rejection, correct resubmission recovery, and same-head rearm compatibility. Acceptance criteria: cross-task evidence returns a safe 4xx before any durable or git mutation; executor defenses remain fail-closed; focused tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 23:07
---
Live corrupting-path reproducer was safely recovered before any foreign commit reached the epic. OOMPAH-602 is resubmitted from its canonical pushed branch; dispatch this child immediately as the final authority/race fix for OOMPAH-585.
---
author: oompah
created: 2026-07-30 23:08
---
Moved to Needs Human from the dashboard/API. Human action required: inspect OOMPAH-629 (Reject cross-task branch evidence before integration mutation), add the specific decision, missing information, or manual fix needed, then move the task back to Open when it is ready for agents again.
---
author: oompah
created: 2026-07-30 23:08
---
Claimed directly under the project owner's instruction to fix race bugs when the server cannot dispatch them. The needs-human marker is an ownership fence against duplicate dispatch while the operator branch is prepared.
---
author: oompah
created: 2026-07-30 23:16
---
Implemented canonical task-branch authority validation before tracker/queue writes and a pre-mutation executor worktree branch fence. Also made checkout failure return before reset. Exact pushed head: 4510fb912aebc99dce90df1dc55e8ee952408401. Verification: 27 focused submission/handoff/executor tests passed; complete Makefile gate passed 13,819 tests with 7 skipped; terminal mutation scan passed.
---
author: oompah
created: 2026-07-30 23:16
---
Reject foreign branch evidence before durable mutation and keep mismatched integration worktrees unchanged.
---
author: oompah
created: 2026-07-30 23:21
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 23:21
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 23:21
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 23:26
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- pushed_head: 4510fb912aebc99dce90df1dc55e8ee952408401
- remote_ref: refs/heads/epic-OOMPAH-585--task-OOMPAH-629
- focused_tests_passed: 27/27
- changed_files: oompah/acp_tools.py, oompah/integration.py, oompah/integration_executor.py, oompah/server.py, tests/test_integration_executor.py, tests/test_task_handoff.py, tests/test_worker_submission.py
- server_validation_call_site: oompah/server.py:2807 (inside _submission_record, called before set_metadata_field/update_issue/enqueue at 3045-3054)
- acp_validation_call_site: oompah/acp_tools.py:711 (before set_metadata_field/update_issue at 739-753)
- executor_fence_call_site: oompah/integration_executor.py:69 (returns wrong_worktree before fetch/checkout/reset)
---
author: oompah
created: 2026-07-30 23:26
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 55
- Tokens: 61 in / 11.3K out [11.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 42s
- Log: OOMPAH-629__20260730T232144Z.jsonl
---
author: oompah
created: 2026-08-02 18:29
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup contains this previously audited Done child; durable integration-queue/rollup evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.
---
<!-- COMMENTS:END -->
