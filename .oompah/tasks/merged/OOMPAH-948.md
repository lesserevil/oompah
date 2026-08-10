---
id: OOMPAH-948
type: bug
status: Merged
priority: 1
title: Bound terminal branch cleanup as durable fair maintenance
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-08-09T09:56:00.569098Z'
updated_at: '2026-08-10T01:16:01.427623Z'
work_branch: OOMPAH-948
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/763
review_number: '763'
review_head: a557d6de3384308a1ae18dd41fec5d12bfb8328a
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-948
  head_sha: a557d6de3384308a1ae18dd41fec5d12bfb8328a
  submitted_at: '2026-08-09T11:38:46.399397+00:00'
  updated_at: '2026-08-09T11:38:46.399397+00:00'
oompah.work_branch: OOMPAH-948
oompah.review_url: https://github.com/lesserevil/oompah/pull/763
oompah.review_number: '763'
oompah.target_branch: main
oompah.review_head: a557d6de3384308a1ae18dd41fec5d12bfb8328a
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-99898cc9a80c
    project_id: proj-14849f1b
    task_id: OOMPAH-948
    digest: ae924b2ff0910c92420dbb0e86d33c5b17ff5beda230d62c4c7b0cd8d45434b4
  - version: 1
    audit_id: audit-1c147ee3beb8
    project_id: proj-14849f1b
    task_id: OOMPAH-948
    digest: ae924b2ff0910c92420dbb0e86d33c5b17ff5beda230d62c4c7b0cd8d45434b4
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-948","audit-99898cc9a80c","attempt-9ff8967af61e"]': '2026-08-09T14:46:28.501589+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-948
    target_state: Done
    evidence_fingerprint: ae924b2ff0910c92420dbb0e86d33c5b17ff5beda230d62c4c7b0cd8d45434b4
    audit_ids:
    - audit-99898cc9a80c
    - audit-1c147ee3beb8
    kind: override
    applied: true
    retired_at: '2026-08-09T14:46:28.501604+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-948
    target_state: Merged
    evidence_fingerprint: ae924b2ff0910c92420dbb0e86d33c5b17ff5beda230d62c4c7b0cd8d45434b4
    audit_ids:
    - audit-99898cc9a80c
    - audit-1c147ee3beb8
    kind: override
    applied: true
    retired_at: '2026-08-10T01:15:59.282489+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-948
    audit_id: audit-99898cc9a80c
    attempt_id: attempt-9ff8967af61e
    target_state: Done
    evidence_fingerprint: ae924b2ff0910c92420dbb0e86d33c5b17ff5beda230d62c4c7b0cd8d45434b4
    status: Needs Human
    audit_ids:
    - audit-99898cc9a80c
    kind: result
    applied: true
    created_at: '2026-08-09T14:46:28.501614+00:00'
    applied_at: '2026-08-09T14:46:35.923212+00:00'
    retired_by_override: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-aa767f34f18b
    project_id: proj-14849f1b
    task_id: OOMPAH-948
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ae924b2ff0910c92420dbb0e86d33c5b17ff5beda230d62c4c7b0cd8d45434b4
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner recovery of stuck Needs Human task: PR #763 exact head
      43531865cb7a8ba62ee5b2310f136e55b57d12e5 passed hosted Python 3.11/3.12/3.13
      CI in run 31314554882 and merged as e8ef2a4c04affdfd1919f906712d21df40538af7.
      The completion auditor ran for 38 minutes and produced only a generic redacted
      operator prompt, not actionable code evidence; the rollout work is already on
      main.'
    created_at: '2026-08-09T16:19:02.155746+00:00'
    selected_ref: a557d6de3384308a1ae18dd41fec5d12bfb8328a
    selected_sha: a557d6de3384308a1ae18dd41fec5d12bfb8328a
    applied: true
  - version: 1
    override_id: override-09b0264e176a
    project_id: proj-14849f1b
    task_id: OOMPAH-948
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ae924b2ff0910c92420dbb0e86d33c5b17ff5beda230d62c4c7b0cd8d45434b4
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Selected or integrated head a557d6d is an ancestor of current main and
      the completed audit evidence is preserved; retire the historical record as Merged.
    created_at: '2026-08-10T01:15:44.220402+00:00'
    selected_ref: a557d6de3384308a1ae18dd41fec5d12bfb8328a
    selected_sha: a557d6de3384308a1ae18dd41fec5d12bfb8328a
    applied: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-99898cc9a80c
    project_id: proj-14849f1b
    task_id: OOMPAH-948
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ae924b2ff0910c92420dbb0e86d33c5b17ff5beda230d62c4c7b0cd8d45434b4
    attempts:
    - version: 1
      attempt_id: attempt-9ff8967af61e
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: ae924b2ff0910c92420dbb0e86d33c5b17ff5beda230d62c4c7b0cd8d45434b4
      created_at: '2026-08-09T14:10:30.590555+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T14:10:30.590555+00:00'
      branch_key: OOMPAH-948
      selected_ref: a557d6de3384308a1ae18dd41fec5d12bfb8328a
      selected_sha: a557d6de3384308a1ae18dd41fec5d12bfb8328a
      verdict: needs_human
      completed_at: '2026-08-09T14:46:28.501498+00:00'
      ended_at: '2026-08-09T14:46:28.501498+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T13:09:07.549841+00:00'
    selected_ref: a557d6de3384308a1ae18dd41fec5d12bfb8328a
    selected_sha: a557d6de3384308a1ae18dd41fec5d12bfb8328a
    updated_at: '2026-08-09T14:46:28.501498+00:00'
  - version: 1
    audit_id: audit-1c147ee3beb8
    project_id: proj-14849f1b
    task_id: OOMPAH-948
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ae924b2ff0910c92420dbb0e86d33c5b17ff5beda230d62c4c7b0cd8d45434b4
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T13:09:07.549841+00:00'
    selected_ref: a557d6de3384308a1ae18dd41fec5d12bfb8328a
    selected_sha: a557d6de3384308a1ae18dd41fec5d12bfb8328a
    updated_at: '2026-08-09T16:19:11.951835+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-9ff8967af61e
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ae924b2ff0910c92420dbb0e86d33c5b17ff5beda230d62c4c7b0cd8d45434b4
    created_at: '2026-08-09T14:10:30.590555+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T14:10:30.590555+00:00'
    branch_key: OOMPAH-948
    selected_ref: a557d6de3384308a1ae18dd41fec5d12bfb8328a
    selected_sha: a557d6de3384308a1ae18dd41fec5d12bfb8328a
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 99
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 10
      output_tokens: 99
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 10
    output_tokens: 99
    cost_usd: 0.0
    recorded_at: '2026-08-09T14:48:36.131485+00:00'
---
## Summary

Triggered by: OOMPAH-947

Live regression observed during the 2026-08-09 OOMPAH-939 rollout: after the orchestrator quiesced at 09:46:21, an already-started maintenance tick walked terminal branch cleanup across the full multi-project historical corpus until at least 09:54:46, logging dozens of nested-parent deferrals and a final 178-branch skip aggregate. This independently holds the event loop and graceful drain for minutes even when audit scanning is bounded. Scope: replace the monolithic terminal branch cleanup sweep with a durable project/task cursor and explicit scheduler-scale operation/time slice; keep exact ownership, accepted-target, shared-epic, nested-topology, and deletion safety fences; persist progress across restart; coalesce an immediate continuation only while eligible cleanup remains; separate bounded actionable work from complete historical observability. Relevant code: orchestrator terminal branch cleanup/maintenance scheduling, project cleanup helpers, workflow maintenance cursors and tick telemetry. Required tests: thousands of terminal/shared/nested rows keep one invocation below the configured deterministic budget; a Ready integration claim progresses between slices; cursor survives restart and visits every project/task fairly; quiesce/drain stops after the current bounded unit; no duplicate or unsafe deletion; partial health remains truthful; existing cleanup safety tests remain green. Acceptance: terminal cleanup cannot monopolize an event-loop tick or graceful restart for minutes, live telemetry shows bounded fair convergence, and complete gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 10:02
---
Additional live evidence: cleanup completed full historical scans at 09:54:46, 09:56:49, and 09:59:29 even though graceful drain quiesced new dispatch at 09:46:21. The configured batch limit counts successful deletions rather than examined rows, so 178 safe skips consume no budget and the cursor resets, causing repeated full scans. Temporary rollout mitigation staged in .env: OOMPAH_WORKTREE_CLEANUP_BATCH_SIZE=0 until this task lands; automated cleanup will be re-enabled immediately after the bounded examined-row cursor is deployed.
---
author: oompah
created: 2026-08-09 10:43
---
Implemented and pushed exact head 08701a192. Cleanup now uses bounded native state pages and durable per-project round-robin cursors across terminal tasks, stale directories, and stale branches; every safe skip/error consumes the operation slice; a 15s cooperative deadline and drain fences yield between exact candidates; partial/error/disabled health is truthful; only budget/deadline deferrals coalesce; cursor saves are checked and serialized; storage cleanup no longer bypasses the worktree lane. Verification: 510 scheduler/config tests and 300 tracker/project/storage tests passed; cold-cache 1,000-task regression parses only the page limit; terminal mutation, secret, diff, and fatal/static scans passed.
---
author: oompah
created: 2026-08-09 10:43
---
Bound worktree cleanup as durable fair maintenance at 08701a192
---
author: oompah
created: 2026-08-09 11:28
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-948`
Target: `main`
Head: `08701a1925d1a6f2a3daf872f22ddda46357540e`
Command: `make test`
Result: `failed`
Process: exited with return code 2
Termination source: `process_exit`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
/python3.12/site-packages/passlib/utils/__init__.py:854: DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13
    from crypt import crypt as _crypt

tests/test_http_auth.py: 21 warnings
  /home/shedwards/.oompah/tmp/oompah-quality-gate-hytabnbj/run/workspace/tests/test_http_auth.py:37: DeprecationWarning: the method passlib.context.CryptContext.encrypt() is deprecated as of Passlib 1.7, and will be removed in Passlib 2.0, use CryptContext.hash() instead.
    return ctx.encrypt("password")

tests/test_http_auth.py::TestVerifyPassword::test_valid_apr1_password
tests/test_http_auth.py::TestVerifyPassword::test_wrong_apr1_password
tests/test_http_auth.py::TestLoadHtpasswdFile::test_valid_multiple_entries
tests/test_http_auth.py::TestVerifierCallable::test_multiple_users
  /home/shedwards/.oompah/tmp/oompah-quality-gate-hytabnbj/run/workspace/tests/test_http_auth.py:49: DeprecationWarning: the method passlib.context.CryptContext.encrypt() is deprecated as of Passlib 1.7, and will be removed in Passlib 2.0, use CryptContext.hash() instead.
    return ctx.encrypt("password")

tests/test_mcp_gateway.py::test_mcp_client_can_initialize_list_allowed_tools_and_call_state
tests/test_mcp_gateway.py::test_authenticated_mcp_client_can_initialize_list_and_call_protected_api
  /home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/contextlib.py:105: DeprecationWarning: Use `streamable_http_client` instead.
    self.gen = func(*args, **kwds)

tests/test_sdk_install_guards.py::TestClaudeSessionMcpServerGuard::test_no_tool_catalog_skips_mcp_server_path
  /home/shedwards/.oompah/tmp/oompah-quality-gate-hytabnbj/run/workspace/oompah/acp_backends/claude.py:532: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    async for msg in client.receive_response():
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_server_release_picks.py::TestPatchReleasePicksEndpoint::test_returns_400_on_invalid_json
tests/test_server_release_picks.py::TestPostApplyReleasePicksToAllChildren::test_returns_400_on_invalid_json
  /home/shedwards/.oompah/tmp/oompah-quality-gate-hytabnbj/run/workspace/.venv/lib/python3.12/site-packages/httpx/_models.py:408: DeprecationWarning: Use 'content=<...>' to upload raw bytes/text content.
    headers, stream = encode_request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_terminal_audit_durable_finalization.py::test_natural_completed_failure_recurrence_replays_fail_closed_disposition
FAILED tests/test_terminal_audit_durable_finalization.py::test_natural_completed_e1_e2_e1_reuses_exact_superseded_pass
FAILED tests/test_terminal_audit_durable_finalization.py::test_non_substantive_max_attempts_owner_rearm_redispatches
FAILED tests/test_terminal_audit_durable_finalization.py::test_natural_exhausted_e1_e2_e1_requires_owner_rearm_before_dispatch
FAILED tests/test_terminal_audit_durable_finalization.py::test_action_required_checkpoint_replays_result_after_restart
FAILED tests/test_terminal_audit_durable_finalization.py::test_evidence_recurrence_dispatches_from_fresh_activation
FAILED tests/test_terminal_audit_durable_finalization.py::test_restart_abandonment_retries_same_candidate_without_duplicate_auditor
FAILED tests/test_terminal_audit_durable_finalization.py::test_completed_done_recurrence_preserves_validation_for_pending_merged
FAILED tests/test_terminal_audit_durable_finalization.py::test_done_result_applied_before_crash_replays_exact_validation_status
FAILED tests/test_terminal_audit_workspace_recovery.py::test_restarted_legacy_binding_failure_exhausts_durably_without_workspace
= 10 failed, 18889 passed, 22 skipped, 2 xfailed, 34 warnings in 151.32s (0:02:31) =

make: *** [Makefile:428: test] Error 1
```
---
author: oompah
created: 2026-08-09 11:33
---
Reproduced the complete-gate failure deterministically: OOMPAH-948 made maintenance cursor updates transactional under _state_io_lock, while two terminal-audit test harnesses bypass Orchestrator.__init__ and did not model that production invariant. This is fixture construction drift, not cleanup state contamination or a terminal-audit product interaction. Updated both partial harnesses to supply the service-state transaction lock; all 55 previously affected terminal-audit durable-finalization/workspace-recovery tests now pass. Running the cleanup-focused suites and complete Makefile gate next.
---
author: oompah
created: 2026-08-09 11:38
---
Complete-gate repair pushed at a557d6de3. Exact cause: the new durable maintenance-cursor transaction correctly uses Orchestrator._state_io_lock; terminal-audit durable-finalization and workspace-recovery partial harnesses construct via __new__ and omitted that production invariant. No cleanup state leak or terminal-audit runtime interaction occurred. Added the missing RLock to both partial harnesses. Verification: 55/55 exact previously failing module tests and 866/866 combined cleanup/config/tracker/project/storage plus terminal-audit tests passed; git diff --check passed. A coordinated full gate is intentionally left to Oompah because other urgent full gates are already running.
---
author: oompah
created: 2026-08-09 11:38
---
Fixed complete-gate fixture regression at a557d6de3; 866 focused tests pass
---
author: oompah
created: 2026-08-09 12:27
---
Branch quality gate passed for `a557d6de3384308a1ae18dd41fec5d12bfb8328a` using `make test` in 158.8s. Review creation may proceed.
---
author: oompah
created: 2026-08-09 12:45
---
Propagated OOMPAH-957 concurrency-test stabilization onto the review branch at 7ab4713ab after hosted Python 3.13 reproduced the exact native-boundary timeout. PR #763 matrix is rerunning.
---
author: oompah
created: 2026-08-09 12:57
---
Refreshed PR #763 onto current main at exact head 43531865c; the OOMPAH-957 timing proof was resolved deterministically and passed 20 repetitions on the identical merged content.
---
author: oompah
created: 2026-08-09 13:09
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 14:10
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 14:10
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 14:46
---
Needs Human — Done audit requires operator input.

[REDACTED] Please review the audit output, decide the next step, and update this task with your instructions.
---
author: oompah
created: 2026-08-09 14:48
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 36, Tool calls: 9
- Tokens: 10 in / 99 out [109 total]
- Cost: $0.0000
- Exit: normal, Duration: 38m 1s
- Log: OOMPAH-948__20260809T141044Z.jsonl
---
author: oompah
created: 2026-08-09 16:19
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Project-owner recovery of stuck Needs Human task: PR #763 exact head 43531865cb7a8ba62ee5b2310f136e55b57d12e5 passed hosted Python 3.11/3.12/3.13 CI in run 31314554882 and merged as e8ef2a4c04affdfd1919f906712d21df40538af7. The completion auditor ran for 38 minutes and produced only a generic redacted operator prompt, not actionable code evidence; the rollout work is already on main.
---
author: oompah
created: 2026-08-09 16:19
---
Directly resolved the stale Needs Human audit after confirming exact-head hosted CI and merged PR #763.
---
author: oompah
created: 2026-08-10 01:15
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Selected or integrated head a557d6d is an ancestor of current main and the completed audit evidence is preserved; retire the historical record as Merged.
---
<!-- COMMENTS:END -->
