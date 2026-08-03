---
id: OOMPAH-627
type: bug
status: Done
priority: 1
title: Preserve integrated evidence when creating auditor worktrees
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T22:09:32.117751Z'
updated_at: '2026-08-03T20:05:01.804020Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-627
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.integration:
  version: 1
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-585--task-OOMPAH-627
  base_branch: epic-OOMPAH-585
  base_sha: d8d265b9a1957560206eec2b4da5d833942c82ea
  head_sha: d8d265b9a1957560206eec2b4da5d833942c82ea
  integrated_sha: d8d265b9a1957560206eec2b4da5d833942c82ea
  submitted_at: '2026-07-30T22:31:48.736186+00:00'
  updated_at: '2026-07-30T23:04:34.839115+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-26df5a1390dc: '2026-07-30T22:29:35.606594+00:00'
    attempt-54ab762046bd: '2026-07-30T23:07:51.453451+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-2e2c6f169bcc
    project_id: proj-14849f1b
    task_id: OOMPAH-627
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 951d87ad1c6853f1732b414ec6f66ec964537326ee8225bafcfbc11e7dad87e9
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup
      contains this previously audited Done child; durable integration-queue/rollup
      evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:28:52.522269+00:00'
    applied: true
    lifecycle_reconciled: true
    reconciled_to: Done
    retired_reason: shared_epic_parent_not_landed
    reconciled_at: '2026-08-03T20:04:59.245612+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-627
    target_state: Merged
    evidence_fingerprint: 951d87ad1c6853f1732b414ec6f66ec964537326ee8225bafcfbc11e7dad87e9
    audit_ids:
    - audit-f823feeddb64
    - audit-c0a68ab5e96e
    kind: override
    applied: false
    retired_at: '2026-08-02T18:29:00.943438+00:00'
    lifecycle_reconciled: true
    reconciled_to: Done
    retired_reason: shared_epic_parent_not_landed
  oompah.terminal_audit_result_intents: []
  oompah.lifecycle_reconciliations:
  - project_id: proj-14849f1b
    task_id: OOMPAH-627
    from: Merged
    to: Done
    reason: shared_epic_parent_not_landed
    conflict: 'Cannot transition shared-epic child OOMPAH-627 to Merged: parent epic
      OOMPAH-585 could not be verified. The parent review must land on its configured
      target branch first.'
    done_audit_ids:
    - audit-c0a68ab5e96e
    created_at: '2026-08-03T20:04:59.245612+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f823feeddb64
    project_id: proj-14849f1b
    task_id: OOMPAH-627
    target_state: Done
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1c24f8149d3f48bd5b0200156ff2675055eed52db9b004b50e36da20f42c9302
    attempts:
    - version: 1
      attempt_id: attempt-26df5a1390dc
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 1c24f8149d3f48bd5b0200156ff2675055eed52db9b004b50e36da20f42c9302
      created_at: '2026-07-30T22:25:54.625821+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T22:25:54.625821+00:00'
      branch_key: OOMPAH-627
      verdict: pass
      completed_at: '2026-07-30T22:29:35.606444+00:00'
      ended_at: '2026-07-30T22:29:35.606444+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T22:25:41.249328+00:00'
    updated_at: '2026-07-30T22:29:35.606444+00:00'
  - version: 1
    audit_id: audit-c0a68ab5e96e
    project_id: proj-14849f1b
    task_id: OOMPAH-627
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f0a137be8ed41a2b2671b76d6dfd91affcf958fd83d28a8ac8b133775344ee90
    attempts:
    - version: 1
      attempt_id: attempt-54ab762046bd
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f0a137be8ed41a2b2671b76d6dfd91affcf958fd83d28a8ac8b133775344ee90
      created_at: '2026-07-30T23:04:48.270691+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T23:04:48.270691+00:00'
      branch_key: epic-OOMPAH-585--task-OOMPAH-627
      verdict: pass
      completed_at: '2026-07-30T23:07:51.453303+00:00'
      ended_at: '2026-07-30T23:07:51.453303+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T23:04:36.015893+00:00'
    updated_at: '2026-07-30T23:07:51.453303+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-26df5a1390dc
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1c24f8149d3f48bd5b0200156ff2675055eed52db9b004b50e36da20f42c9302
    created_at: '2026-07-30T22:25:54.625821+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T22:25:54.625821+00:00'
    branch_key: OOMPAH-627
  - version: 1
    attempt_id: attempt-54ab762046bd
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f0a137be8ed41a2b2671b76d6dfd91affcf958fd83d28a8ac8b133775344ee90
    created_at: '2026-07-30T23:04:48.270691+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T23:04:48.270691+00:00'
    branch_key: epic-OOMPAH-585--task-OOMPAH-627
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-627
oompah.task_costs:
  total_input_tokens: 43
  total_output_tokens: 5755
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 43
      output_tokens: 5755
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 37
    output_tokens: 5626
    cost_usd: 0.0
    recorded_at: '2026-07-30T22:30:04.788596+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 129
    cost_usd: 0.0
    recorded_at: '2026-07-30T23:08:35.142284+00:00'
---
## Summary

Implementation scope: separate completion-auditor workspace creation from implementation-branch initialization for parallel epic children. An auditor must check out the existing task branch without rewriting oompah.work_branch or replacing an integrated oompah.integration record with state working. Preserve normal implementation dispatch behavior and private-branch synchronization. Relevant context: dispatching the OOMPAH-625 auditor at 22:06 recreated its worktree and changed its already-integrated metadata to working, erasing integrated_sha while the audit was in progress. Tests: reproduce workspace creation for an integrated parallel-epic child in auditor mode, assert integration metadata is untouched and the existing private branch is used, assert implementation mode still writes working metadata, and run focused workspace/auditor tests plus the Makefile gate. Acceptance criteria: auditor launch is read-only with respect to integration/work-branch metadata; implementation launch remains unchanged; focused and complete tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 22:09
---
Claimed directly for the active race repair. The human-only label prevents duplicate server dispatch while the operator-owned branch is being prepared.
---
author: oompah
created: 2026-07-30 22:12
---
Implemented an explicit persist_dispatch_metadata boundary. Forced API and ACP auditor setup passes false, so an existing private task branch is checked out without replacing integrated evidence; implementation dispatch retains the prior working-record write. Verification: 33 focused parallel-workspace/ACP/orchestrator tests and 8 ACP handoff tests passed; terminal mutation scan passed.
---
author: oompah
created: 2026-07-30 22:12
---
Keep auditor worktree creation read-only with respect to work-branch and integration metadata.
---
author: oompah
created: 2026-07-30 22:25
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 22:25
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 22:26
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 22:28
---
Audit handoff: exact integrated head 2a8fc4a4b3a101c15e2fea0608480f783f9f3e28 passed the complete Makefile gate. Focused verification also passed 33 parallel-workspace/ACP/orchestrator tests, 8 ACP handoff tests, and the terminal-mutation scan. The live auditor launched just before deployment and therefore reproduced the old metadata overwrite on its own task; that operational metadata will be reflowed after this verdict and restart. Review the code/test evidence on the exact head and submit the structured verdict; do not reimplement.
---
author: oompah
created: 2026-07-30 22:29
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: 2a8fc4a4b3a101c15e2fea0608480f783f9f3e28
- epic_head: 2a8fc4a4b3a101c15e2fea0608480f783f9f3e28
- files_changed: oompah/orchestrator.py, tests/test_acp_agent.py, tests/test_parallel_epic_children.py
- focused_parallel_epic_children: 22 passed
- focused_acp_agent: 71 passed (8 TestAcpWorkerModelHandoff)
- adjacent_orchestrator_auditor: 302 passed (orchestrator_handlers + auditor_dispatch + auditor_contract)
- boundary_call_sites: oompah/orchestrator.py:20768 and 21288 pass persist_dispatch_metadata=not forced_auditor
---
author: oompah
created: 2026-07-30 22:30
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 25
- Tokens: 37 in / 5.6K out [5.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 9s
- Log: OOMPAH-627__20260730T222602Z.jsonl
---
author: oompah
created: 2026-07-30 22:31
---
Reflow after pre-deployment auditor reproduced the fixed metadata race; restore canonical integrated evidence under the deployed protection.
---
author: oompah
created: 2026-07-30 22:31
---
Reflow the already-audited exact head under the deployed auditor-worktree protection so canonical integrated evidence is restored without metadata mutation.
---
author: oompah
created: 2026-07-30 23:04
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 23:04
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 23:07
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: d8d265b9a1957560206eec2b4da5d833942c82ea
- fix_commit: 2a8fc4a4b3a101c15e2fea0608480f783f9f3e28
- files_changed: oompah/orchestrator.py, tests/test_acp_agent.py, tests/test_parallel_epic_children.py
- focused_parallel_epic_children: 22 passed
- focused_acp_agent: 49 passed
- adjacent_orchestrator_handlers_auditor_dispatch_contract: 302 passed
- boundary_call_sites: oompah/orchestrator.py:20778 and 21298 pass persist_dispatch_metadata=not forced_auditor
- guard_line: oompah/orchestrator.py:8245 wraps set_metadata_field with if persist_dispatch_metadata
---
author: oompah
created: 2026-07-30 23:08
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 36, Tool calls: 17
- Tokens: 6 in / 129 out [135 total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 46s
- Log: OOMPAH-627__20260730T230456Z.jsonl
---
author: oompah
created: 2026-08-02 18:28
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup contains this previously audited Done child; durable integration-queue/rollup evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.
---
author: oompah
created: 2026-08-03 20:05
---
Lifecycle reconciliation restored OOMPAH-627 to audited Done: Cannot transition shared-epic child OOMPAH-627 to Merged: parent epic OOMPAH-585 could not be verified. The parent review must land on its configured target branch first.
---
<!-- COMMENTS:END -->
