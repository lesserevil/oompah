---
id: OOMPAH-679
type: bug
status: In Validation
priority: 0
title: Reset activity panel identity when a task starts a new agent run
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-08-01T12:05:24.382952Z'
updated_at: '2026-08-01T15:49:43.586809Z'
work_branch: OOMPAH-679
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/641
review_number: '641'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c2afc418e9d217abf284d9e8a66ead0db5aec54a956ab1276d9a2e851c9b6bfe
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T14:33:49.231152+00:00'
  matched_identifiers: []
  evidence: 'Based on my comprehensive search of the oompah task tracker, I''ve completed
    the duplicate investigation for OOMPAH-679. Let me summarize my findings:


    **Investigation Summary:**


    I searched for related tasks using multiple approaches:

    1. Searched `.oompah/tasks/open/`, `.oompah/tasks/backlog/` - found OOMPAH-281
    (self-hosted runners) and OOMPAH-282 (unicode encoding error) - neither related

    2. Reviewed all merged tasks (OOMPAH-271, 272, 275, 277-280) - all about epic
    rebasing or CI runner setup, none about activity panel or run identity

    3. Searched source code (oompah/) and plans/ for keywords: activity, panel, dashboard,
    running snapshot, run identity, focus_name, focus_role - no matches in active
    code planning

    4. Verified the issue describes a specific live UI regression observed on 2026-08-01
    for task EXOCOMP-143, where the dashboard activity panel failed to reset when
    transitioning from Duplicate Investigator run to Maintenance Engineer run


    **Key Evidence:**

    - OOMPAH-679 is about a regression where activity panel state is keyed by `issue_identifier`
    alone, not by per-run identity

    - The issue requires architectural changes to: expose stable per-run identity,
    reset panel title/cached entries/activity by run_id, handle late activity from
    superseded runs

    - No existing open, backlog, or recent merged tasks cover this specific problem

    - The issue is marked Priority 1, indicating it''s a critical regression

    - Previous comments show duplicate screening was already initiated


    ---


    **Focus handoff: duplicate_detector**


    **Duplicate preflight verdict: no_duplicate**


    **Matches: none**


    **Evidence:** Extensive search of `.oompah/tasks` (open, backlog, merged, archived),
    source code plans/, and implementation files found no existing active task covering
    the activity panel identity reset issue. OOMPAH-281 (self-hosted runners) and
    OOMPAH-282 (unicode error) in open/backlog are unrelated. All merged tasks (271,
    272, 275-280) address epic rebasing or CI infrastructure, not dash'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 2ff497b4-c578-40ac-b287-4a0a568a128e
oompah.task_costs:
  total_input_tokens: 1851739
  total_output_tokens: 22136
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 202
      output_tokens: 5482
      cost_usd: 0.0
    opus:
      input_tokens: 1851537
      output_tokens: 16654
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 202
    output_tokens: 5482
    cost_usd: 0.0
    recorded_at: '2026-08-01T14:33:49.201952+00:00'
  - profile: deep
    model: opus
    input_tokens: 1851497
    output_tokens: 9145
    cost_usd: 0.0
    recorded_at: '2026-08-01T15:18:17.492430+00:00'
  - profile: deep
    model: opus
    input_tokens: 40
    output_tokens: 7509
    cost_usd: 0.0
    recorded_at: '2026-08-01T15:40:21.792339+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-679__20260801T143153Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-679
    source_sha: 62ca0ca696d08b754e03a200d7227455786da960
    completed_at: '2026-08-01T14:33:49.270886+00:00'
  - run_id: OOMPAH-679__20260801T153423Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: opus
    focus: ci_fix
    source_branch: OOMPAH-679
    source_sha: cf050cb8591a3e85855f0879ec4bbf1aa9b7590c
    completed_at: '2026-08-01T15:40:21.797033+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-679
  base_branch: main
  base_sha: 2e24144ff1f12e3f259b1af546d7506851518dc0
  head_sha: cf050cb8591a3e85855f0879ec4bbf1aa9b7590c
  submitted_at: '2026-08-01T15:40:04.440018+00:00'
  updated_at: '2026-08-01T15:40:27.274322+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/641
oompah.review_number: '641'
oompah.work_branch: OOMPAH-679
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f82179cc92d3
    project_id: proj-14849f1b
    task_id: OOMPAH-679
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3b6f79304129fbf181aa3e54c58e68ce4375d0a6cc9f5184b65db1dadd238aee
    attempts:
    - version: 1
      attempt_id: attempt-4cb5c0a64622
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 3b6f79304129fbf181aa3e54c58e68ce4375d0a6cc9f5184b65db1dadd238aee
      created_at: '2026-08-01T15:49:37.322669+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-01T15:49:37.322669+00:00'
      branch_key: OOMPAH-679
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T15:49:11.551264+00:00'
    updated_at: '2026-08-01T15:49:37.322669+00:00'
  - version: 1
    audit_id: audit-b1375f6be9f8
    project_id: proj-14849f1b
    task_id: OOMPAH-679
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3b6f79304129fbf181aa3e54c58e68ce4375d0a6cc9f5184b65db1dadd238aee
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T15:49:11.551264+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-4cb5c0a64622
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3b6f79304129fbf181aa3e54c58e68ce4375d0a6cc9f5184b65db1dadd238aee
    created_at: '2026-08-01T15:49:37.322669+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-01T15:49:37.322669+00:00'
    branch_key: OOMPAH-679
---
## Summary

Live UI regression observed for EXOCOMP-143 on 2026-08-01. A read-only Duplicate Investigator run completed normally at 11:58 with a no-duplicate verdict and zero mutating tool calls. Oompah immediately started a distinct implementation run for the same task with focus_name=chore and focus_role=Maintenance Engineer. The dashboard activity panel continued to show 'Agent: EXOCOMP-143 — Duplicate Investigator · default' while rendering the implementation run's activity, making it appear that the preflight agent violated its role. The client and activity route primarily key state by issue_identifier, which is reused across run boundaries. Implementation scope: expose a stable per-run identity/run id in running snapshots and activity responses; key/reset panel title, cached entries, provider metadata, and polling/WebSocket activity by that identity; update the title even during the brief empty-focus startup state; reject or ignore late activity from superseded runs. Relevant files: orchestrator RunningEntry serialization, /api/v1/state, /api/v1/agents/{identifier}/activity, dashboard activity state/rendering, and WebSocket lifecycle tests. Acceptance criteria: a duplicate-preflight-to-implementation transition on the same task never mixes labels or activity; the old run visibly ends before the new role appears; late old-run events cannot overwrite the new panel; regression coverage reproduces the rapid EXOCOMP-143 transition.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 14:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 14:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 14:33
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 67, Tool calls: 36
- Tokens: 202 in / 5.5K out [5.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 0s
- Log: OOMPAH-679__20260801T143153Z.jsonl
---
author: oompah
created: 2026-08-01 14:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 14:34
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-01 14:34
---
Understanding: the activity panel is keyed by task identifier across agent-run boundaries, so a completed preflight run's title/provider/activity can survive into the next implementation run. I will trace running-state/activity serialization, dashboard state and polling/WebSocket lifecycle, introduce a stable per-run identity with reset/stale-event guards, and add focused transition regression coverage.
---
author: oompah
created: 2026-08-01 14:38
---
Discovery: RunningEntry already has assignment_id only for selected tracker claims, so it is not a universal UI lifecycle key. The API/ACP activity closures and _on_worker_exit only check issue.id, allowing late old-run callbacks/cleanup to target a replacement entry. Dashboard state also updates the open title only when focus_role is truthy, preserving the old role during empty-focus startup. Fix: generated per-dispatch run_id, identity in state/activity/WS, backend callback/exit fencing, and client cache/request/poll reset by run_id.
---
author: oompah
created: 2026-08-01 14:45
---
Implementation: added generated RunningEntry.run_id and propagated it through get_snapshot/get_issue_detail, activity REST, EventBus, and WebSocket messages. API/ACP activity callbacks and _on_worker_exit now reject superseded run IDs before state mutation/cleanup. Dashboard activity state now tracks run_id plus request generation, clears entries/provider/polling on run changes or ended runs, rejects stale pushes/fetches, and renders empty-focus titles without the old role. Added tests/test_activity_run_identity.py.
---
author: oompah
created: 2026-08-01 14:47
---
Verification: focused changed-path suites pass — activity/dashboard 110 passed; WebSocket/EventBus 82 passed; activity identity + candidate/dispatch 81 passed; server auth/WebSocket 128 passed; task handoff 58 passed. Full test_acp_agent.py had 42 passed and 7 environment failures before assertions because its configured agent-log directory is read-only in this sandbox (/home/shedwards/.oompah/agent-logs).
---
author: oompah
created: 2026-08-01 14:53
---
Completion: delivered and pushed df28f5017. Each worker run now has a stable run_id across state/activity/WebSocket APIs; stale callbacks/exits are fenced; the dashboard resets identity-bound title, provider metadata, cache, polling, and fetch generations across duplicate-preflight-to-implementation transitions, including empty-focus startup. Added regression coverage in tests/test_activity_run_identity.py. Focused suites pass; make test could not initialize because the worktree lacks .venv and uv fails with a host DBus transient-scope error.
---
author: oompah
created: 2026-08-01 14:53
---
Reset activity panel identity between sequential agent runs; added run_id propagation, stale-event fencing, dashboard reset logic, and regression tests.
---
author: oompah
created: 2026-08-01 14:54
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 116
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 19m 37s
- Log: OOMPAH-679__20260801T143439Z.jsonl
---
author: oompah
created: 2026-08-01 15:09
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-679`
Target: `main`
Head: `df28f501739ec456e061966015317545b02a7616`
Command: `make test`
Result: `failed`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
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
FAILED tests/test_default_first_dispatch.py::TestDispatchWithDefaultFirstDispatch::test_flag_off_bug_dispatches_deep_profile
FAILED tests/test_default_first_dispatch.py::TestDispatchWithDefaultFirstDispatch::test_flag_on_bug_dispatches_default_profile_first
FAILED tests/test_default_first_dispatch.py::TestDispatchWithDefaultFirstDispatch::test_flag_on_needs_label_bypasses_default_first
FAILED tests/test_default_first_dispatch.py::TestDispatchWithDefaultFirstDispatch::test_flag_on_retry_does_not_override_profile
FAILED tests/test_default_first_dispatch.py::TestDispatchWithDefaultFirstDispatch::test_flag_on_override_profile_bypasses_default_first
FAILED tests/test_default_first_dispatch.py::TestDispatchWithDefaultFirstDispatch::test_flag_on_merge_conflict_label_bypasses_default_first
FAILED tests/test_default_first_dispatch.py::TestDispatchWithDefaultFirstDispatch::test_flag_on_epic_keeps_natural_routing
FAILED tests/test_default_first_dispatch.py::TestDispatchWithDefaultFirstDispatch::test_flag_on_ci_fix_label_bypasses_default_first
FAILED tests/test_default_first_dispatch.py::TestDispatchWithDefaultFirstDispatch::test_flag_on_merge_conflict_keyword_bypasses_default_first
FAILED tests/test_default_first_dispatch.py::TestDispatchWithDefaultFirstDispatch::test_flag_on_unrelated_bug_is_unaffected
FAILED tests/test_default_first_dispatch.py::TestSafetyCriticalAcpRouting::test_carve_out_with_merge_conflict_label
FAILED tests/test_default_first_dispatch.py::TestSafetyCriticalAcpRouting::test_carve_out_with_acp_natural_unchanged
FAILED tests/test_default_first_dispatch.py::TestSafetyCriticalAcpRouting::test_carve_out_with_no_acp_profile_falls_through
FAILED tests/test_default_first_dispatch.py::TestSafetyCriticalAcpRouting::test_carve_out_with_non_acp_natural_swaps_to_acp
FAILED tests/test_default_first_dispatch.py::TestSafetyCriticalAcpRouting::test_carve_out_skipped_when_default_first_dispatch_off
FAILED tests/test_default_first_dispatch.py::TestSafetyCriticalAcpRouting::test_non_carved_out_task_is_unaffected
FAILED tests/test_default_first_dispatch.py::TestSafetyCriticalAcpRouting::test_explicit_handoff_label_skips_swap
FAILED tests/test_default_first_dispatch.py::TestSafetyCriticalAcpRouting::test_retry_does_not_swap_to_acp
FAILED tests/test_duplicate_preflight.py::test_dispatch_preflight_does_not_move_task_in_progress
= 19 failed, 14731 passed, 8 skipped, 1 xfailed, 45 warnings in 393.15s (0:06:33) =

make: *** [Makefile:388: test] Error 1
```
---
author: oompah
created: 2026-08-01 15:11
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-01 15:11
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-01 15:11
---
Understanding: I am repairing the existing OOMPAH-679 review head only. I will sync the same branch, inspect the branch-gate/GitHub check evidence for the 19 dispatch and duplicate-preflight failures, reproduce the focused suites, and apply the smallest tested fix before pushing and resubmitting.
---
author: oompah
created: 2026-08-01 15:13
---
Discovery: the gate failures reproduce exactly. Dispatch now invokes _run_worker(..., run_id=<generated>), but 18 default-first-dispatch test doubles and one duplicate-preflight test double still define the former three-argument coroutine signature, so every failure is TypeError: unexpected keyword argument 'run_id' before assertions. Production behavior is not failing; the minimal repair is to update those focused test doubles and assert the propagated ID matches RunningEntry.run_id.
---
author: oompah
created: 2026-08-01 15:15
---
Implementation: updated the 19 strict dispatch test doubles to accept the new keyword-only run_id contract. The duplicate-preflight test now also records the worker run_id and asserts it matches the registered RunningEntry, preserving coverage of the identity propagation that caused the signature change. No production or workflow code changed in this CI repair.
---
author: oompah
created: 2026-08-01 15:15
---
Verification: scripts/run-tests.sh serial tests/test_default_first_dispatch.py tests/test_duplicate_preflight.py tests/test_activity_run_identity.py passed: 111 passed in 27.93s. This includes every one of the 19 tests named by the failed branch gate plus the run-identity regression suite.
---
author: oompah
created: 2026-08-01 15:17
---
Completion: pushed c24ba48c7 to the existing OOMPAH-679 branch. The minimal CI repair updates only dispatch/preflight test doubles for the run_id keyword and adds an exact worker-to-RunningEntry identity assertion; 111 focused tests pass and the secret scan completed successfully.
---
author: oompah
created: 2026-08-01 15:17
---
Fixed the blocked branch gate by updating strict dispatch and duplicate-preflight test doubles for the run_id worker contract; added an assertion that worker and RunningEntry identities match. Focused suites: 111 passed. Pushed c24ba48c7.
---
author: oompah
created: 2026-08-01 15:18
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 57
- Tokens: 1.9M in / 9.1K out [1.9M total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 10s
- Log: OOMPAH-679__20260801T151111Z.jsonl
---
author: oompah
created: 2026-08-01 15:25
---
Branch quality gate passed for `c24ba48c7516245298b2d68dbf1ddbf0f280f75a` using `make test` in 393.0s. Review creation may proceed.
---
author: oompah
created: 2026-08-01 15:33
---
YOLO: CI tests failed on MR #641. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-08-01 15:34
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-01 15:34
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-01 15:36
---
Understanding: MR #641 CI (test 3.11) failed on tests/test_duplicate_names.py::test_no_duplicate_test_names_in_test_files with 'Failed: Timeout (>5.0s) from pytest-timeout' while ast-parsing tests/test_webhooks.py. The test iterates all 370 test_*.py files under tests/ and ast.parses each. Locally the pass takes ~1s, but under CI xdist load it exceeds the project's 5s default per-test timeout (pyproject.toml [tool.pytest.ini_options] timeout = 5). Neither test_duplicate_names.py nor test_webhooks.py were modified on this branch, so this is CI capacity flakiness surfaced by the growing test corpus. Plan: minimal, precedent-matching fix — add an explicit @pytest.mark.timeout override to test_no_duplicate_test_names_in_test_files (existing tests already use per-test overrides where the default 5s is unrealistic).
---
author: oompah
created: 2026-08-01 15:39
---
Discovery: only failing job on MR #641 is test (3.11) with tests/test_duplicate_names.py::test_no_duplicate_test_names_in_test_files timing out at >5s while ast-parsing tests/test_webhooks.py. Neither the test nor the target file was modified on this branch. Locally the full pass is ~1s (measured across 370 files). The default per-test timeout is 5s; existing tests already override it with @pytest.mark.timeout when the default is unrealistic (7 existing overrides in tests/). Implementation: added @pytest.mark.timeout(60) to test_no_duplicate_test_names_in_test_files with an explanatory comment citing MR #641. No other code changed.
---
author: oompah
created: 2026-08-01 15:39
---
Verification: scripts/run-tests.sh serial tests/test_duplicate_names.py tests/test_default_first_dispatch.py tests/test_duplicate_preflight.py tests/test_activity_run_identity.py — 112 passed in 30.01s. The formerly-flaky test now runs under the raised @pytest.mark.timeout(60) ceiling (measured ~1.87s locally). No other changes.
---
author: oompah
created: 2026-08-01 15:39
---
Completion: pushed cf050cb85 to OOMPAH-679. Minimal CI repair adds a per-test @pytest.mark.timeout(60) override to tests/test_duplicate_names.py::test_no_duplicate_test_names_in_test_files, addressing the MR #641 test (3.11) failure without touching production code or unrelated tests.
---
author: oompah
created: 2026-08-01 15:40
---
Repaired MR #641 CI failure: added @pytest.mark.timeout(60) to test_no_duplicate_test_names_in_test_files (whole-tests-tree AST scan was racing the 5s default under CI xdist contention). No production or feature-test changes.
---
author: oompah
created: 2026-08-01 15:40
---
Agent completed successfully in 362s (7549 tokens)
---
author: oompah
created: 2026-08-01 15:40
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Claude/opus]
- Turns: 48, Tool calls: 34
- Tokens: 40 in / 7.5K out [7.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 2s
- Log: OOMPAH-679__20260801T153423Z.jsonl
---
author: oompah
created: 2026-08-01 15:49
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-01 15:49
---
YOLO: merged PR #641.
---
author: oompah
created: 2026-08-01 15:49
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-01 15:49
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
