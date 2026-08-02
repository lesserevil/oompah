---
id: OOMPAH-684
type: task
status: In Validation
priority: 0
title: Prevent stale retry dispatch after operator task resubmission
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-08-01T21:44:29.390457Z'
updated_at: '2026-08-02T02:20:13.863610Z'
work_branch: OOMPAH-684
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/650
review_number: '650'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 57d3415e0f3269957b9627d45a447cc345e9142b40cdb196449e066c34db7fe9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T21:52:20.259619+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation, I can now provide my findings\
    \ on the duplicate status of OOMPAH-684.\n\n## Investigation Summary\n\nI have\
    \ conducted a thorough search across all task states, documentation, plans, and\
    \ the codebase:\n\n**Search Coverage:**\n- `.oompah/tasks/` directory across all\
    \ states (merged/, archived/, open/, backlog/)\n- Documentation (`docs/`) and\
    \ plans (`plans/`) directories\n- External imports registry\n- Codebase for references\
    \ to retry dispatch, task submission, and generation authority\n\n**Key Findings:**\n\
    \n1. **OOMPAH-661 does not exist** in the current task tracker (neither merged/,\
    \ archived/, open/, nor external imports). The issue description refers to it\
    \ as \"merged,\" but it's not present in the system.\n\n2. **No active task addresses\
    \ the same problem**: I found no open, in-progress, or merged task covering:\n\
    \   - Stale retry dispatch after operator task resubmission\n   - Generation-authority\
    \ invariant for task dispatch\n   - Race conditions between task CLI submit and\
    \ worker dispatch\n   - Ready to Integrate state protection against stale retry\
    \ authority\n   - Atomic cancellation of retries upon successful operator resubmission\n\
    \n3. **Related but distinct tasks** that use \"retry\" involve different systems:\n\
    \   - OOMPAH-211 (Archived): Comment delivery to running agents (different scope)\n\
    \   - OOMPAH-179, OOMPAH-216 (Archived): Release delivery PR polling and retry/archive\
    \ (release delivery system, not task dispatch)\n   - OOMPAH-265 (Archived): Git\
    \ push-race recovery with retries (git infrastructure, not task dispatch)\n  \
    \ - OOMPAH-270 (Archived): Git lock error retries (transient git failures, not\
    \ task authority)\n\n4. **Searched keywords**: \"dispatch\", \"retry\", \"submit\"\
    , \"operator\", \"resubmit\", \"generation\", \"authority\", \"Ready to Integrate\"\
    , \"stale\" \u2014 no matches in active task descriptions or titles that cover\
    \ OOMPAH-684's specific race condition.\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matche"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 5bc2ab90-96ce-41d2-adad-9e861c67e38d
oompah.task_costs:
  total_input_tokens: 425
  total_output_tokens: 22080
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 202
      output_tokens: 6472
      cost_usd: 0.0
    sonnet:
      input_tokens: 173
      output_tokens: 5456
      cost_usd: 0.0
    unknown:
      input_tokens: 50
      output_tokens: 10152
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 202
    output_tokens: 6472
    cost_usd: 0.0
    recorded_at: '2026-08-01T21:52:20.254020+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 173
    output_tokens: 5456
    cost_usd: 0.0
    recorded_at: '2026-08-02T02:12:58.920679+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 50
    output_tokens: 10152
    cost_usd: 0.0
    recorded_at: '2026-08-02T02:19:52.003920+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-684__20260801T214746Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-684
    source_sha: 3d50e86c334e8a6318b767b281bc254fa6d93cc2
    completed_at: '2026-08-01T21:52:20.275034+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-684
  head_sha: 7b160731233e51d6bea57fe65095a6ffa09e760b
  submitted_at: '2026-08-01T23:04:52.785027+00:00'
  updated_at: '2026-08-01T23:04:52.785027+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/650
oompah.review_number: '650'
oompah.work_branch: OOMPAH-684
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-90a88fcf128f: '2026-08-02T02:19:22.350979+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-684
    target_state: Done
    evidence_fingerprint: 958c00bb5699374ae5b7c47ae06ca266f5d34415f36d256acfc32271cee6ea26
    audit_ids:
    - audit-6e5a10195354
    kind: result
    applied: true
    retired_at: '2026-08-02T02:19:22.350991+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-684
    audit_id: audit-6e5a10195354
    attempt_id: attempt-90a88fcf128f
    target_state: Done
    evidence_fingerprint: 958c00bb5699374ae5b7c47ae06ca266f5d34415f36d256acfc32271cee6ea26
    status: In Validation
    audit_ids:
    - audit-6e5a10195354
    applied: true
    created_at: '2026-08-02T02:19:22.351008+00:00'
    applied_at: '2026-08-02T02:19:26.743308+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-6e5a10195354
    project_id: proj-14849f1b
    task_id: OOMPAH-684
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 958c00bb5699374ae5b7c47ae06ca266f5d34415f36d256acfc32271cee6ea26
    attempts:
    - version: 1
      attempt_id: attempt-90a88fcf128f
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 958c00bb5699374ae5b7c47ae06ca266f5d34415f36d256acfc32271cee6ea26
      created_at: '2026-08-02T02:13:04.201854+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T02:13:04.201854+00:00'
      branch_key: OOMPAH-684
      verdict: pass
      completed_at: '2026-08-02T02:19:22.350788+00:00'
      ended_at: '2026-08-02T02:19:22.350788+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Progress
    created_at: '2026-08-02T02:12:41.699584+00:00'
    updated_at: '2026-08-02T02:19:22.350788+00:00'
  - version: 1
    audit_id: audit-379a276e1265
    project_id: proj-14849f1b
    task_id: OOMPAH-684
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 958c00bb5699374ae5b7c47ae06ca266f5d34415f36d256acfc32271cee6ea26
    attempts:
    - version: 1
      attempt_id: attempt-b698464daf77
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 958c00bb5699374ae5b7c47ae06ca266f5d34415f36d256acfc32271cee6ea26
      created_at: '2026-08-02T02:20:06.778657+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T02:20:06.778657+00:00'
      branch_key: OOMPAH-684
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Progress
    created_at: '2026-08-02T02:12:41.699584+00:00'
    updated_at: '2026-08-02T02:20:06.778657+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-90a88fcf128f
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 958c00bb5699374ae5b7c47ae06ca266f5d34415f36d256acfc32271cee6ea26
    created_at: '2026-08-02T02:13:04.201854+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T02:13:04.201854+00:00'
    branch_key: OOMPAH-684
  - version: 1
    attempt_id: attempt-b698464daf77
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 958c00bb5699374ae5b7c47ae06ca266f5d34415f36d256acfc32271cee6ea26
    created_at: '2026-08-02T02:20:06.778657+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T02:20:06.778657+00:00'
    branch_key: OOMPAH-684
---
## Summary

Regression of merged OOMPAH-661 observed on NODEVIRT-7 on 2026-08-01. An operator recovered the preserved worktree, committed validated head bb916af, pushed the assigned branch, and successfully submitted it through the operator-authenticated task CLI. The task entered Ready to Integrate. Roughly three minutes later, stale retry/assignment authority launched implementation run e84dc6296e524e23ac0255bfb692c480 and rewrote the canonical task to In Progress with integration state working, despite the accepted head already being pushed and queued. The redundant worker initially performed only read-only inspection; an operator live handoff told it not to mutate the accepted branch.

This is a direct recurrence of the generation-authority invariant from OOMPAH-661 and must be fixed at the race boundary rather than special-cased.

Implementation scope:
- Trace operator CLI submit through api_submit_issue, native Markdown tracker persistence, retry cancellation, refresh/event coalescing, claimed/running state, and due retry dispatch to identify how stale authority survived.
- Make accepted submission and retry/claim cancellation one atomic authority transition for the exact task generation. A due callback or candidate selected before submission must re-read and reject Ready to Integrate, matching integration metadata/head, replacement assignment, or changed tracker updated_at before it writes In Progress or launches a worker.
- Fence already-starting dispatch setup so a submit that wins before provider launch cancels setup and removes the running/claimed row without tracker rollback.
- If a worker process crosses the boundary, terminate or quarantine it before repository mutation and preserve the accepted Ready to Integrate generation.
- Ensure same-head operator resubmission from Needs Human exercises identical cancellation semantics to a first worker submission.
- Add observability identifying which authority generation lost the race without exposing tokens.

Relevant code: retry authority generation and persisted retries, normal dispatch claim/setup, worker assignment metadata, api_submit_issue/task CLI submission reconciliation, native tracker cache/update ordering, running state, and event-driven refresh.

Required deterministic tests:
- Failed/Needs Human native task is operator-resubmitted at a pushed head while a due retry callback is selected; only Ready to Integrate survives and no worker launches.
- Submit wins during dispatch setup before provider launch; setup aborts without writing In Progress.
- Provider launch crossing the boundary cannot mutate the worktree and accepted head/status are restored automatically.
- Same-head resubmission clears retrying, claimed, running placeholder, integration working metadata, and stale assignment atomically.
- Restart/event coalescing cannot rehydrate the withdrawn retry.
- Unrelated tasks and legitimate post-rejection retries remain unaffected.

Acceptance criteria:
- The exact NODEVIRT-7 sequence cannot redispatch after successful resubmission.
- Ready to Integrate head/status/integration metadata remain authoritative through all tested interleavings.
- Focused retry/submission/dispatch race tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 21:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 21:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 21:52
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 83, Tool calls: 35
- Tokens: 202 in / 6.5K out [6.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 44s
- Log: OOMPAH-684__20260801T214746Z.jsonl
---
author: oompah
created: 2026-08-01 21:53
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 21:53
---
Focus: Callback Auth Validation Specialist
---
author: oompah
created: 2026-08-01 21:53
---
Understanding: stale retry dispatch is surviving operator submission across retry, claim/running, tracker persistence, and event refresh boundaries. I will trace the submission and dispatch paths, identify the shared generation authority transition, add an atomic stale-callback fence and setup/worker quarantine behavior, then cover the listed race interleavings with deterministic tests.
---
author: oompah
created: 2026-08-01 21:57
---
Discovery: _on_retry_timer retains a retry entry during refresh, but _dispatch writes In Progress before its final retry CAS. _cancel_retry_for_issue removes claimed but not claimed_issues and does not quarantine a registered worker. Parallel-epic workspace setup can persist oompah.integration=working before provider launch. The fix will share the per-task transition lock with submission, revoke exact generations, clear claim placeholders, quarantine live workers, and gate workspace metadata writes on live authority.
---
author: oompah
created: 2026-08-01 22:15
---
Implementation: operator submission now shares the per-task transition lock with retry dispatch, revokes exact retry/running generations, clears claimed placeholders and stale assignment metadata, and quarantines workers that cross the acceptance boundary. Workspace/integration setup mutations are authority-guarded; withdrawn shared claims are conditionally removed by run ID. Added deterministic tests for setup cancellation, running-worker quarantine, claim cleanup, and same-head resubmission.
---
author: oompah
created: 2026-08-01 22:23
---
Oompah could not durably preserve this worker's task worktree before retry. The worktree was left in place and no reset, clean, or retry was started. Reconcile the workspace and recovery evidence manually before resuming the task. Error: could not stage recovery snapshot for OOMPAH-684: The following paths are ignored by one of your .gitignore files:
.oompah-no-hooks
hint: Use -f if you really want to add them.
hint: Disable this message with "git config set advice.addIgnoredFile false"
---
author: oompah
created: 2026-08-01 22:47
---
Operator-owned recovery complete at bfcd6f1999dc6739d37c28ef481bce29aee08527. The stale dispatch implementation was preserved, reviewed, committed, and pushed after removing only the generated .oompah-no-hooks helper.\n\nValidation:\n- Focused retry-authority and worker-submission suites: 32 passed.\n- Full make test: 14859 passed, 7 skipped, 1 xfailed in 410.24s.\n- git diff --check passed.\n- Branch is clean and matches origin/OOMPAH-684.\n\nThe Needs Human transition was caused by the ignored generated-helper snapshot defect already fixed canonically by OOMPAH-683; no duplicate follow-up was filed.
---
author: oompah
created: 2026-08-01 22:48
---
Operator recovery complete at bfcd6f199: submission now atomically revokes retry/run authority, clears stale claims, fences workspace mutations, and quarantines crossed workers; focused 32/32 and full 14859-test gates pass.
---
author: oompah
created: 2026-08-01 23:00
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-684`
Target: `main`
Head: `bfcd6f1999dc6739d37c28ef481bce29aee08527`
Command: `make test`
Result: `failed`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
are/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
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
FAILED tests/test_installed_cli_smoke.py::TestCurrentInstallSmoke::test_oompah_help_contains_usage
FAILED tests/test_installed_cli_smoke.py::TestCurrentInstallSmoke::test_oompah_task_help_exits_zero
FAILED tests/test_installed_cli_smoke.py::TestCurrentInstallSmoke::test_oompah_task_view_help_exits_zero
FAILED tests/test_installed_cli_smoke.py::TestCurrentInstallSmoke::test_oompah_task_port_flag_help_exits_zero
FAILED tests/test_installed_cli_smoke.py::TestCurrentInstallSmoke::test_oompah_task_server_flag_help_exits_zero
FAILED tests/test_installed_cli_smoke.py::TestCurrentInstallSmoke::test_oompah_help_exits_zero
FAILED tests/test_installed_cli_smoke.py::TestCurrentInstallSmoke::test_oompah_project_bootstrap_help_exits_zero
FAILED tests/test_installed_cli_smoke.py::TestCurrentInstallSmoke::test_bare_oompah_prints_help_exits_zero
= 8 failed, 14850 passed, 8 skipped, 1 xfailed, 44 warnings in 390.69s (0:06:30) =

/home/shedwards/.oompah/tmp/oompah-quality-gate-ies459lm/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x74012b99f7e0>

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
make: *** [Makefile:388: test] Error 1
```
---
author: oompah
created: 2026-08-01 23:01
---
Infrastructure recovery: the failed branch gate was caused by the trusted service venv's editable source mapping being rewritten to another task worktree, not by bfcd6f199. The service runtime now points back to /home/shedwards/src/oompah; the installed CLI smoke suite passes 13/13. OOMPAH-687 tracks permanent isolation. Reasserting the already clean, pushed, full-gate-passing head for delivery.
---
author: oompah
created: 2026-08-01 23:01
---
Resubmitted clean head bfcd6f199 after repairing the shared branch-gate runtime mapping. Source validation remains 32 focused and 14859 full tests passing; OOMPAH-687 tracks permanent runtime isolation.
---
author: oompah
created: 2026-08-01 23:02
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-01 23:02
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-01 23:03
---
Operator authority reasserted while the stale CI-fix run is registered. Preserve clean pushed head bfcd6f199 and terminate implementation; gate-key recovery follows after runtime repair.
---
author: oompah
created: 2026-08-01 23:03
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 0, Tool calls: 9
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 26s
- Log: OOMPAH-684__20260801T230235Z.jsonl
---
author: oompah
created: 2026-08-01 23:04
---
Empty recovery commit refreshes the exact-head gate key after restoring the trusted service runtime. Source tree is unchanged from bfcd6f199, which passed 32 focused and 14859 full tests.
---
author: oompah
created: 2026-08-02 01:18
---
Branch quality gate passed for `7b160731233e51d6bea57fe65095a6ffa09e760b` using `make test` in 392.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-02 01:26
---
YOLO: CI tests failed on MR #650. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-08-02 01:28
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #3)

**State audited:** `Needs CI Fix`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Recent comment indicates CI is now passing or PR has been merged; safe to reopen for dispatch.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-08-02 01:44
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-02 01:44
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-02 01:45
---
Understanding: CI failures are in tests/test_installed_cli_smoke.py (8 tests: test_oompah_help_contains_usage, test_oompah_task_help_exits_zero, etc.). The branch quality gate blocked due to installed CLI smoke tests failing. Previous comments indicate these failures are a runtime/install isolation issue rather than a source code bug. I will look at the test file, run the failing tests locally, diagnose the root cause, and apply the minimal fix.
---
author: oompah
created: 2026-08-02 02:03
---
Discovery: CI failure is in tests/test_dashboard_task_display_identifier.py::test_api_issues_includes_project_scoped_display_identifier (IndexError: list index out of range at resp.json()["Open"][0]). The clear_api_state autouse fixture is missing 'source_generations': {} and 'invalidated': False from its snapshot reset dict. A previous test can leave _issues_snapshot['source_generations'] = {'proj-X': 'unavailable'}, which causes _issues_snapshot_sources_match to return False → source_stale=True in _issues_snapshot_payload → returns None instead of the correct board. This fix was already applied to origin/main in OOMPAH-683. Fix: add the two missing fields to the clear_api_state fixture.
---
author: oompah
created: 2026-08-02 02:04
---
Implementation: Added 'source_generations': {} and 'invalidated': False to clear_api_state fixture in tests/test_dashboard_task_display_identifier.py (both setup and teardown). This ensures stale source_generations/invalidated state from previous tests cannot contaminate the snapshot state check in _issues_snapshot_payload, which caused source_stale=True and an empty board response. This is the exact fix from OOMPAH-683 that was already on origin/main but missing from this branch.
---
author: oompah
created: 2026-08-02 02:04
---
Verification: Pushed fix to OOMPAH-684 branch (ce27cada4). CI checks are now running on PR #650. The fix: add 'source_generations': {} and 'invalidated': False to clear_api_state fixture's reset dict (both setup and teardown) in tests/test_dashboard_task_display_identifier.py. This prevents stale _issues_snapshot state from a previous test causing source_stale=True and an empty board response. Local tests: 6/6 pass in test_dashboard_task_display_identifier.py; 82/82 pass in test_retry_authority_generation.py and test_submit_queue_concurrency.py.
---
author: oompah
created: 2026-08-02 02:12
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-02 02:12
---
YOLO: merged PR #650.
---
author: oompah
created: 2026-08-02 02:13
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 114
- Tokens: 173 in / 5.5K out [5.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 28m 55s
- Log: OOMPAH-684__20260802T014409Z.jsonl
---
author: oompah
created: 2026-08-02 02:13
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 02:13
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 02:19
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- worktree_head: 7b160731233e51d6bea57fe65095a6ffa09e760b
- branch_head_local: ce27cada4db1cd0d5df67925d40724264eed5439
- origin_main_head: 917633fd9a199f5a456d6b091a72e1a1ad3633b5
- merge_commit: 917633fd9 Merge pull request #650 from lesserevil/OOMPAH-684
- core_fix_commit: bfcd6f199 OOMPAH-684: fence stale dispatch after task submission (5 files, 539+/49-)
- ci_fix_commit: ce27cada4 OOMPAH-684: reset source_generations and invalidated in display-identifier snapshot fixture
- focused_tests_retry_authority: 21 passed in 14.68s
- focused_tests_worker_submission: 11 passed in 2.38s
- focused_tests_dashboard_display: 6 passed in 0.72s
- full_gate: make test passed for 7b160731 (14859 passed / 7 skipped / 1 xfailed in 392.9s)
---
author: oompah
created: 2026-08-02 02:19
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=auditor, role=auditor -> Claude/opus]
- Turns: 63, Tool calls: 44
- Tokens: 50 in / 10.2K out [10.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 46s
- Log: OOMPAH-684__20260802T021310Z.jsonl
---
author: oompah
created: 2026-08-02 02:20
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 02:20
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
