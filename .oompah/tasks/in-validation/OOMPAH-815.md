---
id: OOMPAH-815
type: task
status: In Validation
priority: null
title: Preserve accepted child branch identity across repair dispatch
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T00:29:12.870188Z'
updated_at: '2026-08-05T16:39:56.237647Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-815
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 16b4288530f95cbebd4c56f62ef0f26f61fc0cd1f8b5725bd524b9cadcbce151
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T00:34:07.324585+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: Closest active tasks are OOMPAH-811 (integration rebase/head-generation
    rearming) and OOMPAH-814 (test-fixture determinism). Neither covers the accepted
    child-branch identity split between submission, integration authority, and later
    repair workspace dispatch described here.

    Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none


    Evidence: Closest active tasks are OOMPAH-811 (integration rebase/head-generation
    rearming) and OOMPAH-814 (test-fixture determinism). Neither covers the accepted
    child-branch identity split between submission, integration authority, and later
    repair workspace dispatch described here.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-815
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-763--task-OOMPAH-815
  base_branch: epic-OOMPAH-763
  base_sha: 22252cc0486e919a657d15e5367ce29476622ce3
  head_sha: 5d7cdb7668515ebe0963d59f27c0cca3fcf46dce
  integrated_sha: 5d7cdb7668515ebe0963d59f27c0cca3fcf46dce
  submitted_at: '2026-08-05T15:20:34.216015+00:00'
  updated_at: '2026-08-05T15:46:45.165377+00:00'
oompah.task_costs:
  total_input_tokens: 48362
  total_output_tokens: 12508
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 48168
      output_tokens: 5288
      cost_usd: 0.0
    unknown:
      input_tokens: 194
      output_tokens: 7220
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 48036
    output_tokens: 314
    cost_usd: 0.0
    recorded_at: '2026-08-05T00:34:07.322985+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 132
    output_tokens: 4974
    cost_usd: 0.0
    recorded_at: '2026-08-05T01:10:37.433216+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 55
    output_tokens: 2027
    cost_usd: 0.0
    recorded_at: '2026-08-05T15:51:53.511934+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 139
    output_tokens: 5193
    cost_usd: 0.0
    recorded_at: '2026-08-05T16:39:18.597156+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-815__20260805T003307Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-815
    source_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
    completed_at: '2026-08-05T00:34:07.357924+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-cdb3a68f1765
    project_id: proj-14849f1b
    task_id: OOMPAH-815
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a26816809a2ddf483c46696bb3cb32e37f1ccc0374a87dd6f015032624afc144
    attempts:
    - version: 1
      attempt_id: attempt-6259cc99f102
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a26816809a2ddf483c46696bb3cb32e37f1ccc0374a87dd6f015032624afc144
      created_at: '2026-08-05T15:47:22.524129+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T15:47:22.524129+00:00'
      branch_key: epic-OOMPAH-763--task-OOMPAH-815
      failure_classification: policy_incompatibility
      ended_at: '2026-08-05T15:51:56.908796+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-05T15:52:06.908770+00:00'
    - version: 1
      attempt_id: attempt-afeb2ebe6a4b
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a26816809a2ddf483c46696bb3cb32e37f1ccc0374a87dd6f015032624afc144
      created_at: '2026-08-05T15:52:25.425222+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-05T15:52:25.425222+00:00'
      branch_key: epic-OOMPAH-763--task-OOMPAH-815
      candidate_rotation_count: 1
      failure_classification: policy_incompatibility
      ended_at: '2026-08-05T16:39:20.268831+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-05T16:39:40.268802+00:00'
    - version: 1
      attempt_id: attempt-b6dbbb065cc8
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a26816809a2ddf483c46696bb3cb32e37f1ccc0374a87dd6f015032624afc144
      created_at: '2026-08-05T16:39:54.584609+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-05T16:39:54.584609+00:00'
      branch_key: epic-OOMPAH-763--task-OOMPAH-815
      candidate_rotation_count: 2
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-05T15:46:48.635769+00:00'
    updated_at: '2026-08-05T16:39:54.584609+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-6259cc99f102
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a26816809a2ddf483c46696bb3cb32e37f1ccc0374a87dd6f015032624afc144
    created_at: '2026-08-05T15:47:22.524129+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T15:47:22.524129+00:00'
    branch_key: epic-OOMPAH-763--task-OOMPAH-815
    failure_classification: policy_incompatibility
    ended_at: '2026-08-05T15:51:56.908796+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-05T15:52:06.908770+00:00'
  - version: 1
    attempt_id: attempt-afeb2ebe6a4b
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a26816809a2ddf483c46696bb3cb32e37f1ccc0374a87dd6f015032624afc144
    created_at: '2026-08-05T15:52:25.425222+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-05T15:52:25.425222+00:00'
    branch_key: epic-OOMPAH-763--task-OOMPAH-815
    candidate_rotation_count: 1
    failure_classification: policy_incompatibility
    ended_at: '2026-08-05T16:39:20.268831+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-05T16:39:40.268802+00:00'
  - version: 1
    attempt_id: attempt-b6dbbb065cc8
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a26816809a2ddf483c46696bb3cb32e37f1ccc0374a87dd6f015032624afc144
    created_at: '2026-08-05T16:39:54.584609+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-05T16:39:54.584609+00:00'
    branch_key: epic-OOMPAH-763--task-OOMPAH-815
    candidate_rotation_count: 2
---
## Summary

Live reproduction on OOMPAH-814 at 2026-08-05 00:26 UTC: a direct-owner implementation was validly submitted and recorded in oompah.integration with task_branch=OOMPAH-814 and exact head cb1446d4, while the issue work_branch remained null. After the exact full gate failed and the server dispatched a CI repair, workspace setup recomputed epic-OOMPAH-763--task-OOMPAH-814, found the registered OOMPAH-814 worktree on the accepted branch, refused to reset it, and failed before the worker started. The same split identity can affect any manually/directly submitted epic child and repeats on every repair. Implementation scope: define one canonical immutable accepted branch identity across owner claim, task submit validation, integration record, issue work_branch metadata, workspace registry, retry/recovery dispatch, and terminal audit. Either reject a noncanonical child branch before mutating tracker/queue, or safely persist and reuse a valid accepted branch; never recompute a different branch after acceptance. Preserve exact remote-head verification, parent-base containment, worktree no-reset safety, concurrent submission fencing, and existing hierarchical child branches. Required tests: exact OOMPAH-814 plain-branch submit then Needs CI Fix repair; restart before repair; null/stale work_branch; canonical hierarchical control; remote branch/head mismatch rejection; dirty/divergent registered worktree preservation; concurrent resubmit; OOMPAH-813-style branch; and no retry loop or duplicate worker. Acceptance: an accepted submission can always be repaired/audited on the same proven branch, invalid branches fail before queue/tracker mutation, and workspace setup never disagrees with persisted integration authority.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 00:32
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-08-05 00:32
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 00:34
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 0
- Tokens: 48.0K in / 314 out [48.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 24s
- Log: OOMPAH-815__20260805T003307Z.jsonl
---
author: oompah
created: 2026-08-05 00:35
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-05 00:35
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-05 00:36
---
Understanding: This task fixes a bug where accepted child branch identity is not preserved across repair dispatch. Root cause: when a direct-owner submits an epic child task on a plain branch (e.g., OOMPAH-814), the submission records task_branch=OOMPAH-814 in oompah.integration but leaves issue work_branch as null. On CI repair, workspace setup recomputes the canonical branch name (epic-OOMPAH-763--task-OOMPAH-814), which differs from the accepted branch (OOMPAH-814), causing a conflict with the registered worktree. Fix: persist the accepted branch identity at submission time and reuse it on repair/retry dispatch, never recomputing it. Starting with code exploration to find root cause.
---
author: oompah
created: 2026-08-05 00:45
---
Independent read-only audit found the exact contract: OOMPAH-576 safety guards work; its legacy expected_submission_branch fallback accepts identifier when work_branch is null. _persist_worker_submission then writes integration but never work_branch. Later _create_workspace_for_issue unconditionally derives the hierarchical child branch and overwrites accepted authority. Once IntegrationRecord has task_branch+head_sha, that pair must win and Issue.work_branch is only a projection; submission should atomically reconcile it, retry/workspace/audit must reuse it, and fresh unsubmitted dispatch may still derive hierarchy. Centralize the resolver across server normal/scoped/ACP submit, _create_workspace_for_issue, _retry_issue_branch, and audit branch key. OOMPAH-813 is the live regression shape (accepted OOMPAH-813 at eb5d with null work_branch); preserve OOMPAH-814's current hierarchical workaround. Add zero-mutation mismatch/concurrency/restart/no-reset regressions; do not weaken ProjectStore/integration-executor safety.
---
author: oompah
created: 2026-08-05 00:46
---
Containment detail: _git_submission_evidence uses merge-base only for changed paths and does not return base_sha; _submission_record only syntax-checks inherited/supplied base_sha and does not verify ancestry. If accepting/reusing a parented null-metadata branch, add server-authoritative read-only proof that origin/<submitted branch> exists at submitted head and the head is compatible with/descends from the expected recorded parent base before any tracker/queue write. Otherwise reject pre-mutation. The executor's later fetch/rebase guard is necessary but does not meet this task's pre-mutation acceptance.
---
author: oompah
created: 2026-08-05 01:07
---
Acceptance detail for same-head resubmission: _persist_worker_submission currently returns early when the integration record is unchanged and status is Ready. Reconcile/backfill Issue.work_branch from the accepted non-working IntegrationRecord before that early return, or include branch projection agreement in the idempotency condition. Otherwise legacy null/stale work_branch rows remain vulnerable after an idempotent resubmit. Add exact regression for same task_branch/head with null and conflicting stale work_branch, proving accepted integration authority wins and the projection is repaired atomically.
---
author: oompah
created: 2026-08-05 01:10
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 92
- Tokens: 132 in / 5.0K out [5.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 35m 21s
- Log: OOMPAH-815__20260805T003530Z.jsonl
---
author: oompah
created: 2026-08-05 02:32
---
Review found a remaining Ready-to-Integrate set-status/status-label bypass around the unified submit transaction. Forward repair is pushed at 3b96e04bb03da5da724199945997c5ba15c831b7: task-scoped ACP/API and scoped HTTP now reject Ready aliases and label equivalents with the must-use-submit diagnostic before mutation. 34 focused tests pass; awaiting independent re-review.
---
author: oompah
created: 2026-08-05 14:16
---
Corrected implementation is clean and pushed at exact head ccd1bf4550b67bbaaf21589d15550f31e9f1f6a7 on exact epic base 22252cc0486e919a657d15e5367ce29476622ce3. It persists and binds accepted submission authority before revocation, contains post-accept assignment cleanup failure, routes natural and scheduled retirement through the accepted fence, preserves the accepted branch across live/restart/forced recovery, and uses accepted branch+SHA for terminal-audit locks/fingerprints. Focused verification: 642 executions on the first correction plus 131 adjacent scheduler/submission/provider executions on the final delta; real scheduled ACP retirement regression passes; terminal mutation scan 8/8, secret and diff checks pass. Independent exact-head review PASS at ccd1bf455 after two blocking review rounds; branch/upstream/base/trailers exact.
---
author: oompah
created: 2026-08-05 14:16
---
Preserve accepted branch and submission authority through repair, audit, restart, and retirement
---
author: oompah
created: 2026-08-05 14:33
---
The combined-tree quality gate failed on `epic-OOMPAH-763--task-OOMPAH-815`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
/lib/python3.12/asyncio/unix_events.py", line 568, in close
      self._close(None)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
      self._loop.call_soon(self._call_connection_lost, exc)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

tests/test_websocket_authenticated_bootstrap.py::TestWebSocketBootstrapIncludesAuth::test_ws_bootstrap_includes_service_instance_id
  /home/shedwards/.oompah/tmp/oompah-quality-gate-mu2awcfx/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x71afca4b39c0>
  
  Traceback (most recent call last):
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
      self.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 104, in close
      proto.pipe.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 568, in close
      self._close(None)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
      self._loop.call_soon(self._call_connection_lost, exc)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_project_locks.py::TestConcurrentWorktreeOperationsAreSerialized::test_create_and_remove_same_project_are_serialized
FAILED tests/test_project_locks.py::TestDifferentProjectsAreIndependent::test_two_projects_create_worktree_concurrently
FAILED tests/test_project_locks.py::TestConcurrentWorktreeOperationsAreSerialized::test_two_create_worktree_calls_same_project_are_serialized
FAILED tests/test_project_locks.py::TestEpicWorktreeLocking::test_create_epic_and_create_regular_same_project_are_serialized
FAILED tests/test_project_locks.py::TestConcurrentMaintenanceAndDispatch::test_maintenance_remove_and_dispatch_create_are_serialized
FAILED tests/test_project_locks.py::TestConcurrentMaintenanceAndDispatch::test_maintenance_and_dispatch_different_projects_run_concurrently
FAILED tests/test_project_locks.py::TestConcurrentMaintenanceAndDispatch::test_thread_pool_concurrent_operations_same_project_serialized
FAILED tests/test_project_locks.py::TestLockReleasedOnError::test_lock_released_after_create_worktree_raises
= 8 failed, 15999 passed, 8 skipped, 1 xfailed, 55 warnings in 999.09s (0:16:39) =

make: *** [Makefile:401: test] Error 1

```
---
author: oompah
created: 2026-08-05 15:20
---
Independent incremental review PASS at exact head 5d7cdb7668515ebe0963d59f27c0cca3fcf46dce. Delta from previously approved ccd1bf455 is test-only: exactly eight project-lock mock side effects accept the two keyword-only ProjectStore arguments; runtime and assertions are unchanged, and the real per-project lock remains exercised. Verification: five full lock-suite repetitions (130/130), 188 focused projects/recovery tests, terminal scan 8/8, secret scan, diff check, canonical trailer, clean exact upstream.
---
author: oompah
created: 2026-08-05 15:20
---
Fixed the eight stale project-lock test doubles exposed by the canonical full gate; repeated focused verification and independent exact-head review pass at 5d7cdb7668515ebe0963d59f27c0cca3fcf46dce.
---
author: oompah
created: 2026-08-05 15:46
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 15:47
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 15:47
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 15:51
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 38
- Tokens: 55 in / 2.0K out [2.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 29s
- Log: OOMPAH-815__20260805T154736Z.jsonl
---
author: oompah
created: 2026-08-05 15:52
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
author: oompah
created: 2026-08-05 15:52
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-05 15:52
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 15:56
---
Audit-infrastructure note for any later retry: OOMPAH-831/OOMPAH-832 track a deployed tool-contract bug. Use the advertised search_files/read_file tools with one literal pattern at a time and already-approved git status/log/show/branch/rev-parse/diff commands; do not use git ls-remote, git for-each-ref, wc, arbitrary scripting, or compound output redirection. This is tool guidance only, not a requested verdict; exact-head evidence and acceptance judgment remain the auditor’s.
---
author: oompah
created: 2026-08-05 16:39
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 0, Tool calls: 98
- Tokens: 139 in / 5.2K out [5.3K total]
- Cost: $0.0000
- Exit: terminated, Duration: 46m 51s
- Log: OOMPAH-815__20260805T155238Z.jsonl
---
author: oompah
created: 2026-08-05 16:39
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
<!-- COMMENTS:END -->
