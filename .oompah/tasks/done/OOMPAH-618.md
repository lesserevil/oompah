---
id: OOMPAH-618
type: bug
status: Done
priority: 1
title: Keep ACP shell commands off the scheduler event loop
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:03:01.411786Z'
updated_at: '2026-08-03T20:04:16.713400Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-618
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-618
  base_branch: epic-OOMPAH-585
  base_sha: 58915e5f0b116cf4269f6bb882dd81aa4010ec03
  updated_at: '2026-07-30T21:22:30.155761+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-10c30103c602: '2026-07-30T21:26:07.485406+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-f023a174d359
    project_id: proj-14849f1b
    task_id: OOMPAH-618
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 521a5d8c31d24272c4a8f758e501311e515f603c49a1dd0608080fd759993c89
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup
      contains this previously audited Done child; durable integration-queue/rollup
      evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:27:34.651738+00:00'
    applied: true
    lifecycle_reconciled: true
    reconciled_to: Done
    retired_reason: shared_epic_parent_not_landed
    reconciled_at: '2026-08-03T20:04:14.272216+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-618
    target_state: Merged
    evidence_fingerprint: 521a5d8c31d24272c4a8f758e501311e515f603c49a1dd0608080fd759993c89
    audit_ids:
    - audit-9d800f698a24
    kind: override
    applied: false
    retired_at: '2026-08-02T18:27:40.969145+00:00'
    lifecycle_reconciled: true
    reconciled_to: Done
    retired_reason: shared_epic_parent_not_landed
  oompah.terminal_audit_result_intents: []
  oompah.lifecycle_reconciliations:
  - project_id: proj-14849f1b
    task_id: OOMPAH-618
    from: Merged
    to: Done
    reason: shared_epic_parent_not_landed
    conflict: 'Cannot transition shared-epic child OOMPAH-618 to Merged: parent epic
      OOMPAH-585 could not be verified. The parent review must land on its configured
      target branch first.'
    done_audit_ids:
    - audit-9d800f698a24
    created_at: '2026-08-03T20:04:14.272216+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-9d800f698a24
    project_id: proj-14849f1b
    task_id: OOMPAH-618
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 34e97871777f8d8185691d0089611298ba88e2995780542a26eb2d3c7886c7a0
    attempts:
    - version: 1
      attempt_id: attempt-10c30103c602
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 34e97871777f8d8185691d0089611298ba88e2995780542a26eb2d3c7886c7a0
      created_at: '2026-07-30T21:22:26.182799+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T21:22:26.182799+00:00'
      branch_key: OOMPAH-618
      verdict: pass
      completed_at: '2026-07-30T21:26:07.485224+00:00'
      ended_at: '2026-07-30T21:26:07.485224+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T21:22:10.374704+00:00'
    updated_at: '2026-07-30T21:26:07.485224+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-10c30103c602
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 34e97871777f8d8185691d0089611298ba88e2995780542a26eb2d3c7886c7a0
    created_at: '2026-07-30T21:22:26.182799+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T21:22:26.182799+00:00'
    branch_key: OOMPAH-618
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-618
oompah.task_costs:
  total_input_tokens: 65
  total_output_tokens: 2229
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 65
      output_tokens: 2229
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 65
    output_tokens: 2229
    cost_usd: 0.0
    recorded_at: '2026-07-30T21:26:23.175712+00:00'
---
## Summary

Implementation scope: fix the live scheduler stall reproduced while the OOMPAH-616 completion auditor ran a long test command. The Claude/OpenCode and Codex ACP run_command tools are async wrappers but currently invoke api_agent._exec_run_command synchronously on the orchestrator event-loop thread. Offload every subprocess-backed run_command execution to a worker thread while preserving direct in-process oompah task command routing, authority checks, timeouts, output formatting, and auditor read-only rules. Relevant file: oompah/acp_tools.py and ACP catalog tests. Tests: deterministically capture the thread identity used by each distinct ACP run_command implementation and assert the subprocess helper never runs on the event-loop thread; cover Claude/OpenCode shared catalog and Codex catalog, normal output, direct task command interception, and timeout behavior. Run focused ACP tests and Oompah's full combined-tree gate. Acceptance criteria: a long agent or auditor shell command does not stop scheduler refresh, integration completion, audit dispatch, or API-state updates; all three catalog builders retain compatible results; tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:04
---
Claimed for direct operator implementation. This child fixes the event-loop stall observed during the OOMPAH-616 audit; implementation, regression tests, branch integration, and audit handoff will be completed here.
---
author: oompah
created: 2026-07-30 21:08
---
Implemented on commit 58915e5f0. Claude, Codex, and OpenCode run_command subprocess helpers now execute via asyncio.to_thread while direct task commands remain in-process. Verification: 53 project-tool tests passed; 367 ACP-related tests passed; terminal mutation scan passed.
---
author: oompah
created: 2026-07-30 21:08
---
Moved subprocess-backed ACP run_command execution off the scheduler event loop for Claude, Codex, and OpenCode, with deterministic thread-boundary regressions and focused ACP verification.
---
author: oompah
created: 2026-07-30 21:21
---
Completion-auditor handoff: focused verification already passed (53 project-tool tests, 367 ACP-related tests, terminal mutation scan). The integration executor is now running the exact combined-tree full gate; once this task is marked In Validation/integrated, that queue transition is evidence that the full gate passed. Inspect the three asyncio.to_thread boundaries and deterministic thread-identity regressions; do not redundantly rerun the full suite on the old server, whose inline run_command behavior is the bug this task fixes.
---
author: oompah
created: 2026-07-30 21:22
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 21:22
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 21:22
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 21:26
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_commit: 58915e5f0b116cf4269f6bb882dd81aa4010ec03
- integration_branch_head: 58915e5f0b116cf4269f6bb882dd81aa4010ec03
- files_changed: oompah/acp_tools.py, tests/test_acp_project_tools.py
- to_thread_call_sites: oompah/acp_tools.py:1124 (Claude), 1431 (Codex), 1734 (OpenCode)
- regression_tests: tests/test_acp_project_tools.py:633 (Claude), 1017 (Codex), 1043 (OpenCode)
- focused_tests_passed: 53 acp_project_tools + 240 combined acp + 18 server_blocking_off_loop + 140 authority/dispatch
---
author: oompah
created: 2026-07-30 21:26
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 43
- Tokens: 65 in / 2.2K out [2.3K total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 56s
- Log: OOMPAH-618__20260730T212234Z.jsonl
---
author: oompah
created: 2026-08-02 18:27
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup contains this previously audited Done child; durable integration-queue/rollup evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.
---
author: oompah
created: 2026-08-03 20:04
---
Lifecycle reconciliation restored OOMPAH-618 to audited Done: Cannot transition shared-epic child OOMPAH-618 to Merged: parent epic OOMPAH-585 could not be verified. The parent review must land on its configured target branch first.
---
<!-- COMMENTS:END -->
