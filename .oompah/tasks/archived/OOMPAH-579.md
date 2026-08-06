---
id: OOMPAH-579
type: task
status: Archived
priority: null
title: Prune branchless terminal legacy epic-task worktrees
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T03:54:54.485192Z'
updated_at: '2026-08-06T04:56:15.904552Z'
work_branch: OOMPAH-579
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/591
review_number: '591'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8ccb18c9f5940ac30b5b05d69de5e8b93464e2e2b55f3bb6bda3cac6cd52d40a
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T03:57:15.515900+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: OOMPAH-578 and OOMPAH-561 are terminal historical tasks. Active OOMPAH-576,
    OOMPAH-459, OOMPAH-489, OOMPAH-281, and OOMPAH-282 cover distinct integration,
    auditing, CI, or migration concerns.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 0f81df32-5dec-411c-99ac-8eae3640cda0
oompah.task_costs:
  total_input_tokens: 836143
  total_output_tokens: 30681
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 835929
      output_tokens: 3294
      cost_usd: 0.0
    unknown:
      input_tokens: 214
      output_tokens: 27387
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 835643
    output_tokens: 3233
    cost_usd: 0.0
    recorded_at: '2026-07-30T03:57:15.514800+00:00'
  - profile: default
    model: haiku
    input_tokens: 286
    output_tokens: 61
    cost_usd: 0.0
    recorded_at: '2026-07-30T04:03:11.012705+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 73
    output_tokens: 19950
    cost_usd: 0.0
    recorded_at: '2026-07-30T04:31:01.996769+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 128
    output_tokens: 4921
    cost_usd: 0.0
    recorded_at: '2026-07-30T04:40:30.176959+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 13
    output_tokens: 2516
    cost_usd: 0.0
    recorded_at: '2026-08-06T04:56:13.431565+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-579__20260730T035552Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-579
    source_sha: 98c6189d302507cd77248d1fd54ad723e0166fde
    completed_at: '2026-07-30T03:57:15.524576+00:00'
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: OOMPAH-579
  head_sha: a994cad2c31d26067b8942c58b15b02e9b457a13
  submitted_at: '2026-07-30T04:10:53.032640+00:00'
  updated_at: '2026-07-30T04:10:53.032640+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/591
oompah.review_number: '591'
oompah.work_branch: OOMPAH-579
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-251e79e4565b: '2026-07-30T04:26:50.105440+00:00'
    attempt-7ef7db1b6f50: '2026-07-30T04:40:15.958825+00:00'
    attempt-8ed80ade4fd0: '2026-08-06T04:55:09.092589+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-579
    target_state: Archived
    evidence_fingerprint: 041557e3a675910e9b6b42c59de3d8b97d6b1d0734565d684163e40a0553d4cb
    audit_ids:
    - audit-761d8231b229
    kind: result
    applied: true
    retired_at: '2026-08-06T04:55:09.092600+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-579
    audit_id: audit-761d8231b229
    attempt_id: attempt-8ed80ade4fd0
    target_state: Archived
    evidence_fingerprint: 041557e3a675910e9b6b42c59de3d8b97d6b1d0734565d684163e40a0553d4cb
    status: Archived
    audit_ids:
    - audit-761d8231b229
    applied: true
    created_at: '2026-08-06T04:55:09.092615+00:00'
    applied_at: '2026-08-06T04:55:20.324613+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-8000b84dffe3
    project_id: proj-14849f1b
    task_id: OOMPAH-579
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b6e8fb4fba77b922ef08a752d764e4e91181eed333ccc726812affdc1ff0f1b1
    attempts:
    - version: 1
      attempt_id: attempt-251e79e4565b
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b6e8fb4fba77b922ef08a752d764e4e91181eed333ccc726812affdc1ff0f1b1
      created_at: '2026-07-30T04:20:09.070799+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T04:20:09.070799+00:00'
      branch_key: OOMPAH-579
      verdict: pass
      completed_at: '2026-07-30T04:26:50.105325+00:00'
      ended_at: '2026-07-30T04:26:50.105325+00:00'
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T04:20:02.983899+00:00'
    updated_at: '2026-07-30T04:26:50.105325+00:00'
  - version: 1
    audit_id: audit-12a22c80c49c
    project_id: proj-14849f1b
    task_id: OOMPAH-579
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b6e8fb4fba77b922ef08a752d764e4e91181eed333ccc726812affdc1ff0f1b1
    attempts:
    - version: 1
      attempt_id: attempt-7ef7db1b6f50
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b6e8fb4fba77b922ef08a752d764e4e91181eed333ccc726812affdc1ff0f1b1
      created_at: '2026-07-30T04:31:47.080885+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T04:31:47.080885+00:00'
      branch_key: OOMPAH-579
      verdict: pass
      completed_at: '2026-07-30T04:40:15.958708+00:00'
      ended_at: '2026-07-30T04:40:15.958708+00:00'
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T04:20:02.983899+00:00'
    updated_at: '2026-07-30T04:40:15.958708+00:00'
  - version: 1
    audit_id: audit-761d8231b229
    project_id: proj-14849f1b
    task_id: OOMPAH-579
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 041557e3a675910e9b6b42c59de3d8b97d6b1d0734565d684163e40a0553d4cb
    attempts:
    - version: 1
      attempt_id: attempt-8ed80ade4fd0
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 041557e3a675910e9b6b42c59de3d8b97d6b1d0734565d684163e40a0553d4cb
      created_at: '2026-08-06T04:52:07.255893+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-06T04:52:07.255893+00:00'
      branch_key: OOMPAH-579
      verdict: pass
      completed_at: '2026-08-06T04:55:09.092402+00:00'
      ended_at: '2026-08-06T04:55:09.092402+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-06T04:48:57.570868+00:00'
    updated_at: '2026-08-06T04:55:09.092402+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-251e79e4565b
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b6e8fb4fba77b922ef08a752d764e4e91181eed333ccc726812affdc1ff0f1b1
    created_at: '2026-07-30T04:20:09.070799+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T04:20:09.070799+00:00'
    branch_key: OOMPAH-579
  - version: 1
    attempt_id: attempt-7ef7db1b6f50
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b6e8fb4fba77b922ef08a752d764e4e91181eed333ccc726812affdc1ff0f1b1
    created_at: '2026-07-30T04:31:47.080885+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T04:31:47.080885+00:00'
    branch_key: OOMPAH-579
  - version: 1
    attempt_id: attempt-8ed80ade4fd0
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 041557e3a675910e9b6b42c59de3d8b97d6b1d0734565d684163e40a0553d4cb
    created_at: '2026-08-06T04:52:07.255893+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-06T04:52:07.255893+00:00'
    branch_key: OOMPAH-579
---
## Summary

Triggered by live verification of OOMPAH-578. Implementation scope: when a Merged/Archived non-epic task has no work_branch metadata, detect the old Oompah layout only if its exact managed epic-<same-task-identifier> worktree directory exists; use that exact branch/worktree as the cleanup candidate. Do not infer arbitrary branches, shared parent epic branches, or unregistered paths. Relevant code: oompah/projects.py and tests/test_projects.py. Tests: run the real bare-remote legacy cleanup scenario both with explicit legacy branch metadata and with branch_name omitted; prove worktree/local/remote refs are removed, while shared-parent and arbitrary branches remain rejected. Acceptance criteria: archived OOMPAH-310-style workspaces are pruned on the normal cleanup pass without widening ownership beyond exact managed same-identifier paths; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 03:55
---
Live reproduction confirmed OOMPAH-310 is Archived with work_branch unset while its exact managed epic-OOMPAH-310 worktree and branch remain. Implemented same-identifier managed-path fallback only; testing explicit and absent metadata paths against a real bare remote.
---
author: oompah
created: 2026-07-30 03:55
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 03:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 03:57
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 13
- Tokens: 835.6K in / 3.2K out [838.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 28s
- Log: OOMPAH-579__20260730T035552Z.jsonl
---
author: oompah
created: 2026-07-30 03:57
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 03:57
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-30 04:00
---
The full gate reproduced the unrelated 1-second maintenance-lane wall-clock flake fixed at OOMPAH-459 commit 95581aca5 (13,618 other tests passed). Carried the identical structural 60s-vs-15s stabilization so this branch can pass its required gate now; repeated the formerly flaky test 10/10 successfully and kept the structural non-blocking assertion unchanged.
---
author: oompah
created: 2026-07-30 04:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 17
- Tokens: 286 in / 61 out [347 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 46s
- Log: OOMPAH-579__20260730T035729Z.jsonl
---
author: oompah
created: 2026-07-30 04:10
---
Implemented narrow fallback cleanup for terminal task records with missing branch metadata when an exact managed epic-<same-id> legacy worktree exists. Added real bare-remote coverage for recorded and branchless forms; full make test passes (13,619 passed, 7 skipped). Commit a994cad2c pushed.
---
author: oompah
created: 2026-07-30 04:20
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 04:20
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 04:20
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 04:26
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- implementation_commit: a994cad2c31d26067b8942c58b15b02e9b457a13
- merge_commit: 3aa2bd65bebf902b96e933e845352b1a8b98fbe7
- merged_to_main: true
- focused_tests: tests/test_projects.py::TestRemoveWorktreeCleanup 16 passed
- changed_files: oompah/projects.py, tests/test_projects.py, tests/test_client_auth.py, tests/test_orchestrator_handlers.py
- scope_guardrails: fallback gated on not is_epic AND os.path.isdir(epic_worktree_path_for(same identifier)); legacy_epic_task gate enforces candidate==epic_branch_name(same identifier); _remove_epic_worktree_locked called with the same task identifier
---
author: oompah
created: 2026-07-30 04:31
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 96, Tool calls: 67
- Tokens: 73 in / 19.9K out [20.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 10m 51s
- Log: OOMPAH-579__20260730T042018Z.jsonl
---
author: oompah
created: 2026-07-30 04:31
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 04:31
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 04:40
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- implementation_commit: a994cad2c31d26067b8942c58b15b02e9b457a13
- merge_commit: 3aa2bd65bebf902b96e933e845352b1a8b98fbe7
- merged_to_main: true
- focused_tests: tests/test_projects.py::TestRemoveWorktreeCleanup all passing
- changed_files: oompah/projects.py, tests/test_projects.py, tests/test_client_auth.py
- scope_guardrails: fallback gated on not is_epic AND os.path.isdir(epic_worktree_path_for(same identifier)); candidate is epic_branch_name(same identifier); legacy_epic_task gate unchanged; _remove_epic_worktree_locked called with the same task identifier
- test_parametrization: recorded_branch in ['epic-TASK-42', None] against real bare remote
---
author: oompah
created: 2026-07-30 04:40
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 91
- Tokens: 128 in / 4.9K out [5.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 42s
- Log: OOMPAH-579__20260730T043150Z.jsonl
---
author: oompah
created: 2026-08-06 04:52
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-06 04:52
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-06 04:55
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- implementation_commit: a994cad2c31d26067b8942c58b15b02e9b457a13
- merge_commit: 3aa2bd65bebf902b96e933e845352b1a8b98fbe7
- merged_to_main: true
- merge_pr: #591
- previous_terminal_audits: pass to Done and pass to Merged
- focused_tests: tests/test_projects.py::TestRemoveWorktreeCleanup all passing (previously 16 passed)
- changed_files: oompah/projects.py, tests/test_projects.py
- scope_guardrails: fallback gated on not is_epic AND os.path.isdir(epic_worktree_path_for(same identifier)); candidate == epic_branch_name(same identifier); _remove_epic_worktree_locked called with same identifier; legacy_epic_task gate unchanged
- test_parametrization: recorded_branch in ['epic-TASK-42', None] against real bare remote; shared-parent and arbitrary branches remain rejected
- archive_safety: merge commit is ancestor of origin/main; work is fully integrated
---
author: oompah
created: 2026-08-06 04:56
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 11, Tool calls: 7
- Tokens: 13 in / 2.5K out [2.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 0s
- Log: OOMPAH-579__20260806T045221Z.jsonl
---
<!-- COMMENTS:END -->
